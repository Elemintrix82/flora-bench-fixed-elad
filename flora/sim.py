"""sim.py - event-driven simulation of one node-day for a given policy."""
from __future__ import annotations
import numpy as np
from . import energy as en
from .traffic import generate, link_trace, state_at, LINK_PHY, LINK_BER, CLASSES, STREAMS
from .policies import TAG_FLOOR_BITS, APPROVED, REC_HDR, Floor

CONN_INTERVAL = 0.05    # s, BLE connection interval (ASSUMPTION)
GUARD_BASE = 0.3        # s, fixed flush guard before the earliest deadline
GUARD_K = 4.0           # guard also covers GUARD_K x expected air time of the buffer (link-adaptive)
BUF_CAP = 4000          # bytes of plaintext buffered at most (RAM budget)


def run_day(policy, env, seed, crypto: en.CryptoCost, ber_mult=1.0, horizon=86400.0,
            recs=None, trace=None, battery=None, log_frames=False, ber_trace=None):
    rng = np.random.default_rng(seed)
    recs = generate(rng, horizon) if recs is None else recs
    trace = link_trace(rng, env, horizon) if trace is None else trace
    battery = rng.uniform(10, 100) if battery is None else battery
    prng = np.random.default_rng(seed + 7919)
    policy.reset(prng, env, battery)
    E_crypto = E_radio = 0.0
    n_frames = 0
    lat = {c: [] for c in CLASSES}
    miss = {c: 0 for c in CLASSES}
    viol_tag = {c: 0 for c in CLASSES}
    nonstd = {c: 0 for c in CLASSES}
    count = {c: 0 for c in CLASSES}
    air_bytes = 0
    frames = []

    def bm(t):   # BER multiplier at time t (ber_trace: per-minute multiplier, e.g. a jamming window)
        if ber_trace is None:
            return ber_mult
        return ber_mult * ber_trace[min(int(t // 60.0), len(ber_trace) - 1)]

    def flush(t_send, q):
        nonlocal E_crypto, E_radio, n_frames, air_bytes
        link = state_at(trace, t_send)
        cls_list = [CLASSES[r["cls"]] for r in q]
        pt = sum(int(r["size"]) + REC_HDR for r in q)
        cipher, tag, hdr, pt_padded, alg_vis = policy.frame(cls_list, pt, link)
        ec = crypto.energy(cipher, pt_padded)
        sdu = hdr + pt_padded + tag
        phy, ber = LINK_PHY[link], LINK_BER[link] * bm(t_send)
        er, t_air = 0.0, 0.0
        for L in en.ll_fragments(sdu):
            per = min(en.packet_error_rate(phy, L, ber), 0.999)
            tries = prng.geometric(1 - per)
            er += tries * en.attempt_energy(phy, L)
            t_air += (tries - 1) * CONN_INTERVAL   # one connection interval per retransmission
            t_air += tries * (en.airtime(phy, L) + en.T_IFS)
        t_done = t_send + prng.uniform(0, CONN_INTERVAL) + t_air
        E_crypto += ec; E_radio += er; n_frames += 1; air_bytes += sdu
        m = 0
        for r, c in zip(q, cls_list):
            l = t_done - r["t"]
            lat[c].append(l); count[c] += 1
            if l > r["deadline"]:
                miss[c] += 1; m += 1
            if tag * 8 < TAG_FLOOR_BITS[c]:
                viol_tag[c] += 1
            if c in ("R", "V") and cipher not in APPROVED:
                nonstd[c] += 1
        policy.feedback((ec + er) * 1e6 / len(q), m)
        if log_frames:
            frames.append((t_send, sdu, int("V" in cls_list), int("R" in cls_list), cls_list[0], alg_vis or ""))

    base = getattr(policy, "inner", policy)          # unwrap recording wrappers
    is_floor = isinstance(base, Floor) or getattr(base, "deadline_aware", False)
    queue, flush_at = [], np.inf
    for r in recs:
        t = r["t"]
        while queue and flush_at <= t:
            flush(flush_at, queue); queue, flush_at = [], np.inf
        if not policy.batching:
            flush(t, [r]); continue
        if not queue:
            w = policy.window(state_at(trace, t), r["deadline"])
            flush_at = (np.floor(t / base.slot) + 1) * base.slot if w is None else t + w
        queue.append(r)
        if is_floor:
            link = state_at(trace, t)
            _, tg, hd, padded, _ = base.frame([CLASSES[x["cls"]] for x in queue],
                                                sum(int(x["size"]) + REC_HDR for x in queue), link)
            qbytes = padded + tg + hd
            _, _, t_exp = en.expected_radio_energy(LINK_PHY[link], qbytes, LINK_BER[link] * bm(t))
            guard = GUARD_BASE + GUARD_K * t_exp + CONN_INTERVAL
            dl = min(x["t"] + x["deadline"] for x in queue)
            flush_at = min(flush_at, dl - guard)
        if sum(int(x["size"]) + REC_HDR for x in queue) >= BUF_CAP:
            flush(t, queue); queue, flush_at = [], np.inf
    if queue:
        flush(min(flush_at, horizon), queue)
    tot = sum(count.values())
    out = {
        "policy": policy.name, "env": env, "seed": seed, "ber_mult": ber_mult,
        "E_crypto_J": E_crypto, "E_radio_J": E_radio, "E_total_J": E_crypto + E_radio,
        "frames": n_frames, "air_bytes": air_bytes, "records": tot,
        "crypto_share": E_crypto / (E_crypto + E_radio),
    }
    for c in CLASSES:
        out[f"n_{c}"] = count[c]
        out[f"miss_{c}"] = miss[c]
        out[f"viol_tag_{c}"] = viol_tag[c]
        out[f"nonstd_{c}"] = nonstd[c]
        out[f"lat_p95_{c}"] = float(np.quantile(lat[c], 0.95)) if lat[c] else np.nan
    return (out, frames) if log_frames else out
