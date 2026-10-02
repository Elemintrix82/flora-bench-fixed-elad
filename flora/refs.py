"""refs.py - independent host reference implementations used to verify every
firmware build (known-answer and cross-implementation tests)."""
from __future__ import annotations
import hmac, hashlib, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from . import pyascon_ref

SBOX = [0x6, 0x5, 0xC, 0xA, 0x1, 0xE, 0x7, 0x9, 0xB, 0x0, 0x3, 0xD, 0x8, 0xF, 0x4, 0x2]
RC = [0x01, 0x02, 0x04, 0x09, 0x12, 0x05, 0x0b, 0x16, 0x0c, 0x19, 0x13, 0x07, 0x0f,
      0x1f, 0x1e, 0x1c, 0x18, 0x11, 0x03, 0x06, 0x0d, 0x1b, 0x17, 0x0e, 0x1d]


def _rotl(x, r, w):
    return ((x << r) | (x >> (w - r))) & ((1 << w) - 1)


def _subcolumn(rows, ncols):
    """Apply the 4-bit S-box to the first `ncols` columns (bit j of rows 0..3)."""
    out = list(rows)
    for j in range(ncols):
        v = sum(((rows[i] >> j) & 1) << i for i in range(4))
        s = SBOX[v]
        for i in range(4):
            out[i] = (out[i] & ~(1 << j)) | (((s >> i) & 1) << j)
    return out


def rectangle128_encrypt_block(block: bytes, key: bytes) -> bytes:
    """RECTANGLE-64/128 written from the specification (column S-box lookup)."""
    kr = [int.from_bytes(key[4 * i:4 * i + 4], "little") for i in range(4)]
    subkeys = []
    for r in range(26):
        subkeys.append([k & 0xFFFF for k in kr])
        if r == 25:
            break
        kr = _subcolumn(kr, 8)
        r0, r1, r2, r3 = kr
        kr = [_rotl(r0, 8, 32) ^ r1, r2, _rotl(r2, 16, 32) ^ r3, r0]
        kr[0] ^= RC[r]
    w = [int.from_bytes(block[2 * i:2 * i + 2], "little") for i in range(4)]
    for r in range(25):
        w = [w[i] ^ subkeys[r][i] for i in range(4)]
        w = _subcolumn(w, 16)
        w = [w[0], _rotl(w[1], 1, 16), _rotl(w[2], 12, 16), _rotl(w[3], 13, 16)]
    w = [w[i] ^ subkeys[25][i] for i in range(4)]
    return b"".join(x.to_bytes(2, "little") for x in w)


def rectangle_ctr_hmac_encrypt(k32: bytes, n4: bytes, ad: bytes, m: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(m), 8):
        ks = rectangle128_encrypt_block(n4 + (i // 8).to_bytes(4, "little"), k32[:16])
        out += bytes(a ^ b for a, b in zip(m[i:i + 8], ks))
    tag = hmac.new(k32[16:32], ad + n4 + bytes(out), hashlib.sha256).digest()
    return bytes(out) + tag


def reference_encrypt(variant: str, k: bytes, n: bytes, ad: bytes, m: bytes) -> bytes | None:
    if variant.startswith("ascon"):
        return pyascon_ref.ascon_encrypt(k[:16], n[:16], ad, m, variant="Ascon-AEAD128")
    if variant == "aesgcm":
        return AESGCM(k[:16]).encrypt(n[:12], m, ad)
    if variant == "chacha20poly1305":
        return ChaCha20Poly1305(k[:32]).encrypt(n[:12], m, ad)
    if variant == "rectangle_ctr_hmac":
        return rectangle_ctr_hmac_encrypt(k[:32], n[:4], ad, m)
    return None  # GIFT-COFB and Xoodyak are checked against their official KAT files


def parse_kat(path: str):
    """Parse a NIST LWC KAT file into a list of dicts (Key, Nonce, PT, AD, CT)."""
    entries, cur = [], {}
    for line in open(path):
        line = line.strip()
        if not line:
            if cur:
                entries.append(cur); cur = {}
            continue
        k, _, v = line.partition("=")
        cur[k.strip()] = v.strip()
    if cur:
        entries.append(cur)
    return entries
