"""energy.py - energy model of one IoMT node (nRF52840-class SoC, BLE link).

All constants come from the nRF52840 Product Specification v1.5 (Nordic
Semiconductor, 2021) and the Bluetooth Core Specification v5.x (Vol 6, Part B)
unless marked ASSUMPTION. The crypto cost comes from experiment 01
(instruction-level Cortex-M4 cycle model).
"""
from __future__ import annotations
import os
import numpy as np, pandas as pd
from .config import OUT

V_SUPPLY = 3.0            # V
I_CPU_PER_MHZ = 52e-6     # A/MHz, CoreMark from flash, DC/DC (PS v1.5, 5.2.1)
F_CPU = 64e6              # Hz
I_TX = 4.8e-3             # A, TX 0 dBm, DC/DC (PS v1.5 feature list)
I_RX = 4.6e-3             # A, RX 1 Mbps, DC/DC (PS v1.5 feature list); used for all PHYs (ASSUMPTION)
T_RAMP = 40e-6            # s, fast ramp-up tTXEN,FAST = tRXEN,FAST (PS, RADIO timing)
T_IFS = 150e-6            # s, inter frame space (Core Spec Vol 6 Part B 4.1.1)
LL_MAX_PAYLOAD = 251      # bytes with LE Data Length Extension
L2CAP_ATT_HDR = 7         # L2CAP (4) + ATT handle-value notification (3)
E_CYCLE = V_SUPPLY * I_CPU_PER_MHZ * (F_CPU / 1e6) / F_CPU   # J per CPU cycle

PHYS = ("2M", "1M", "S2", "S8")


def airtime(phy: str, ll_payload: int) -> float:
    """Air time (s) of one LL data packet carrying `ll_payload` bytes (Core Spec 5.x, 2.1-2.2)."""
    if phy == "1M":
        return 8e-6 * (1 + 4 + 2 + ll_payload + 3)
    if phy == "2M":
        return 4e-6 * (2 + 4 + 2 + ll_payload + 3)
    S = 2 if phy == "S2" else 8
    return 1e-6 * (80 + 256 + 16 + 24 + S * 8 * (2 + ll_payload + 3) + 3 * S)


TRANSPORT = os.environ.get("FLORA_TRANSPORT", "coc")   # "att_unbounded" = v1.1 model
L2CAP_HDR = 4             # L2CAP basic header, present in every K-frame
SDU_LEN = 2               # SDU length field, first K-frame of an SDU only
MPS = LL_MAX_PAYLOAD - L2CAP_HDR   # 247: one K-frame per LL packet
ATT_MAX_VALUE = LL_MAX_PAYLOAD - L2CAP_ATT_HDR   # 244 with ATT_MTU = 247


def ll_fragments(sdu_bytes: int) -> list[int]:
    """LL payload sizes needed to carry one AEAD frame of `sdu_bytes` bytes.

    v1.1 ("att_unbounded") charged 7 bytes once per frame and cut the result at 251 bytes, i.e. it
    treated a frame of up to 4 kB as a single ATT notification, which ATT does not allow (a
    notification carries at most ATT_MTU - 3 bytes, and an attribute value at most 512 bytes).
    Default ("coc"): a frame that fits one notification (<= 244 B with ATT_MTU 247) is sent as an ATT
    notification (4 + 3 bytes); a longer frame is sent as one SDU of an LE credit-based L2CAP
    channel, segmented into K-frames of MPS = 247 bytes (4-byte L2CAP header in every K-frame,
    2-byte SDU length in the first), one K-frame per LL packet (Core Spec Vol 3 Part A 3.4)."""
    if TRANSPORT == "att_unbounded":
        total = sdu_bytes + L2CAP_ATT_HDR
        n = max(1, -(-total // LL_MAX_PAYLOAD))
        return [LL_MAX_PAYLOAD] * (n - 1) + [total - LL_MAX_PAYLOAD * (n - 1)]
    if sdu_bytes <= ATT_MAX_VALUE:
        return [sdu_bytes + L2CAP_ATT_HDR]
    info = sdu_bytes + SDU_LEN
    n = -(-info // MPS)
    return [MPS + L2CAP_HDR] * (n - 1) + [info - MPS * (n - 1) + L2CAP_HDR]


def attempt_energy(phy: str, ll_payload: int) -> float:
    """Energy (J) of one TX attempt + IFS + reception of the peer's empty ACK packet."""
    e_tx = V_SUPPLY * I_TX * (T_RAMP + airtime(phy, ll_payload))
    e_rx = V_SUPPLY * I_RX * (T_RAMP + T_IFS + airtime(phy, 0))
    return e_tx + e_rx


def packet_error_rate(phy: str, ll_payload: int, ber: float) -> float:
    bits = 8 * (ll_payload + 2 + 3) + (0 if phy in ("1M", "2M") else 0)
    return 1.0 - (1.0 - ber) ** bits


def expected_radio_energy(phy: str, sdu_bytes: int, ber: float, max_tries: int = 50):
    """Expected radio energy (J), expected attempts and air time for one SDU with ARQ."""
    e = att = t = 0.0
    for L in ll_fragments(sdu_bytes):
        per = min(packet_error_rate(phy, L, ber), 0.999)
        n = 1.0 / (1.0 - per)
        e += n * attempt_energy(phy, L)
        att += n
        t += n * (airtime(phy, L) + T_IFS + airtime(phy, 0) + T_IFS)
    return e, att, t


class CryptoCost:
    """Cycle cost of AEAD encryption, interpolated from experiment 01 results."""
    def __init__(self, path: str | None = None):
        path = path or os.path.join(OUT, "results/01_crypto_cost.csv")
        df = pd.read_csv(path)
        self.tab = {v: (g.msg_len.to_numpy(float), g.enc_cycles.to_numpy(float))
                    for v, g in df.groupby("variant")}

    def cycles(self, variant: str, msg_len: int) -> float:
        x, y = self.tab[variant]
        if msg_len <= x[-1]:
            return float(np.interp(msg_len, x, y))
        slope = (y[-1] - y[-2]) / (x[-1] - x[-2])
        return float(y[-1] + slope * (msg_len - x[-1]))

    def energy(self, variant: str, msg_len: int) -> float:
        return self.cycles(variant, msg_len) * E_CYCLE
