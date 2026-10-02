"""traffic.py - synthetic but standard-grounded telemetry of a wearable IoMT node.

Record sizes follow the Bluetooth SIG GATT characteristic formats (Heart Rate
Measurement, PLX Spot-check Measurement, CGM Measurement); ECG uses 250 Hz x
12-bit samples. Classes follow HL7 v3 Confidentiality codes: N (normal),
R (restricted), V (very restricted). Periods, episode duty cycles and
deadlines are scenario ASSUMPTIONS (config table in the article).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

DAY = 86400.0
CLASSES = ("N", "R", "V")


@dataclass(frozen=True)
class Stream:
    name: str
    cls: str
    sizes: tuple[int, ...]   # possible payload sizes (bytes), drawn uniformly
    kind: str                # periodic | episodic | poisson | daily
    period: float            # s (periodic / episodic chunk period)
    deadline: float          # s, maximum delivery latency
    rate: float = 0.0        # events/s (poisson)
    duty: tuple[float, float] = (0.0, 0.0)   # episodic: (on seconds, cycle seconds)
    times: tuple[float, ...] = ()            # daily: nominal times (s since midnight)


STREAMS = (
    Stream("hr", "N", (2, 4, 6), "periodic", 1.0, 5.0),
    Stream("spo2", "N", (5, 7, 9), "periodic", 60.0, 60.0),
    Stream("cgm", "R", (6, 10, 13, 15), "periodic", 300.0, 300.0),
    Stream("ecg", "R", (375,), "episodic", 1.0, 10.0, duty=(600.0, 3600.0)),
    Stream("alert", "R", (12,), "poisson", 0.0, 1.0, rate=1 / 10800.0),
    Stream("adherence", "V", (16,), "daily", 0.0, 300.0, times=(8 * 3600.0, 20 * 3600.0)),
    Stream("phq", "V", (48,), "daily", 0.0, 3600.0, times=(21 * 3600.0,)),
)


PROFILES = {
    "patch": STREAMS,                                                     # multi-parameter patch (main scenario)
    "vitals": tuple(x for x in STREAMS if x.name != "ecg"),               # vital signs only, no ECG
    "holter": tuple(Stream(x.name, x.cls, x.sizes, x.kind, x.period, x.deadline, x.rate, (3600.0, 3600.0), x.times)
                    if x.name == "ecg" else x for x in STREAMS if x.name in ("hr", "ecg", "alert", "adherence")),
}


def generate(rng: np.random.Generator, horizon: float = DAY, streams=STREAMS):
    """Return a time-sorted structured array of records (t, size, cls_idx, deadline, stream_idx)."""
    recs = []
    for si, s in enumerate(streams):
        if s.kind == "periodic":
            t = np.arange(rng.uniform(0, s.period), horizon, s.period)
        elif s.kind == "episodic":
            on, cyc = s.duty
            starts = np.arange(rng.uniform(0, cyc), horizon, cyc)
            t = np.concatenate([np.arange(a, min(a + on, horizon), s.period) for a in starts]) if len(starts) else np.array([])
        elif s.kind == "poisson":
            n = rng.poisson(s.rate * horizon)
            t = np.sort(rng.uniform(0, horizon, n))
        else:  # daily events with +-20 min jitter
            t = np.array([x + rng.uniform(-1200, 1200) for x in s.times if x < horizon])
            t = t[(t >= 0) & (t < horizon)]
        size = rng.choice(s.sizes, len(t))
        for ti, sz in zip(t, size):
            recs.append((ti, int(sz), CLASSES.index(s.cls), s.deadline, si))
    arr = np.array(recs, dtype=[("t", "f8"), ("size", "i4"), ("cls", "i4"), ("deadline", "f8"), ("stream", "i4")])
    return np.sort(arr, order="t")


# ---- link context: Markov chain on link quality with 60-s steps
LINK_STATES = ("good", "fair", "poor")
LINK_PHY = {"good": "2M", "fair": "1M", "poor": "S8"}      # BLE adaptive PHY choice
LINK_BER = {"good": 1e-6, "fair": 1e-5, "poor": 1e-4}      # ASSUMPTION (sensitivity analysis x0.1..x10)
LINK_RSSI = {"good": -60.0, "fair": -80.0, "poor": -95.0}  # dBm, used by the Elad et al. rule
ENVIRONMENTS = {  # stationary distribution of link states (ASSUMPTION)
    "hospital": (0.85, 0.12, 0.03),
    "home": (0.40, 0.50, 0.10),
    "rural": (0.05, 0.30, 0.65),
}
STEP = 60.0
STAY = 0.95


def link_trace(rng: np.random.Generator, env: str, horizon: float = DAY):
    pi = np.array(ENVIRONMENTS[env])
    n = int(np.ceil(horizon / STEP)) + 1
    s = np.empty(n, dtype=int)
    s[0] = rng.choice(3, p=pi)
    for i in range(1, n):
        s[i] = s[i - 1] if rng.random() < STAY else rng.choice(3, p=pi)
    return s  # state index per minute


def state_at(trace, t: float) -> str:
    return LINK_STATES[trace[min(int(t // STEP), len(trace) - 1)]]
