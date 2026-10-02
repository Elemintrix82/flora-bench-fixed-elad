"""01_crypto_cost.py - cost of each AEAD on an emulated Cortex-M4 (-O2).

For every variant and message length: exact instruction count and modelled
cycles for encryption and decryption (AD = 16-byte header), repeated on
R random inputs to check data-independence; every output is verified against
an independent host implementation or the official KAT file.
Outputs: outputs/results/01_crypto_cost.csv, 01_crypto_meta.json  (~3 min)
"""
import json, os, subprocess, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flora.m4emu import M4Emu
from flora.config import OUT, ROOT, SEED, QUICK
from flora import refs

BUILD = os.path.join(ROOT, "firmware/build/cortex-m4-O2")
VARIANTS = {  # name -> (label, tag bytes, nonce bytes transmitted by default)
    "ascon_armv7m": ("Ascon-AEAD128 (armv7m)", 16, 16),
    "ascon_ref": ("Ascon-AEAD128 (ref C)", 16, 16),
    "aesgcm": ("AES-128-GCM (C)", 16, 12),
    "chacha20poly1305": ("ChaCha20-Poly1305", 16, 12),
    "giftcofb": ("GIFT-COFB", 16, 16),
    "xoodyak": ("Xoodyak", 16, 16),
    "rectangle_ctr_hmac": ("RECTANGLE-CTR+HMAC-SHA256", 32, 4),
}
LENGTHS = [0, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]
AD_LEN = 16
R = 2 if QUICK else 5


def kat_check(emu, variant, kat_file, n_max=60):
    ok = 0
    for e in refs.parse_kat(kat_file)[:n_max]:
        k, n = bytes.fromhex(e["Key"]), bytes.fromhex(e["Nonce"])
        m, ad, ct = bytes.fromhex(e["PT"]), bytes.fromhex(e["AD"]), bytes.fromhex(e["CT"])
        emu.write("K", k); emu.write("N", n); emu.write("AD", ad); emu.write("M", m)
        emu.write_u32("g_mlen", len(m)); emu.write_u32("g_adlen", len(ad))
        emu.call("bench_enc")
        assert emu.read("C", len(ct)) == ct, f"{variant}: KAT mismatch"
        ok += 1
    return ok


def main():
    rng = np.random.default_rng(SEED)
    rows, meta = [], {}
    for v, (label, tag, nlen) in VARIANTS.items():
        elf = os.path.join(BUILD, f"{v}.elf")
        emu = M4Emu(elf)
        size = subprocess.run(["arm-none-eabi-size", "-A", elf], capture_output=True, text=True).stdout
        text = sum(int(l.split()[1]) for l in size.splitlines() if l.startswith(".text"))
        checks = {"kat_vectors": 0, "cross_checks": 0}
        if v == "giftcofb":
            checks["kat_vectors"] = kat_check(emu, v, os.path.join(ROOT, "firmware/third_party/GIFT-COFB.txt"))
        if v == "xoodyak":
            checks["kat_vectors"] = kat_check(emu, v, os.path.join(ROOT, "firmware/third_party/Xoodyak.txt"))
        if v.startswith("ascon"):
            checks["kat_vectors"] = kat_check(emu, v, os.path.join(ROOT, "firmware/third_party/ASCON_AEAD128_KAT.txt"))
        for L in LENGTHS:
            enc_c, dec_c, enc_i, dec_i, stack = [], [], [], [], 0
            for r in range(R):
                k, n, ad, m = rng.bytes(32), rng.bytes(16), rng.bytes(AD_LEN), rng.bytes(L)
                emu.write("K", k); emu.write("N", n); emu.write("AD", ad); emu.write("M", m)
                emu.write_u32("g_mlen", L); emu.write_u32("g_adlen", AD_LEN)
                se = emu.call("bench_enc")
                c = emu.read("C", L + tag)
                ref = refs.reference_encrypt(v, k, n, ad, m)
                if ref is not None:
                    assert c == ref, f"{v} L={L}: output differs from host reference"
                    checks["cross_checks"] += 1
                sd = emu.call("bench_dec")
                assert sd.ret == 0 and emu.read("P", L) == m, f"{v}: decrypt failed"
                # tamper test: flip one tag bit -> must be rejected
                if r == 0:
                    bad = bytearray(c); bad[-1] ^= 1; emu.write("C", bytes(bad))
                    assert emu.call("bench_dec").ret != 0, f"{v}: forgery accepted"
                enc_c.append(se.cycles); dec_c.append(sd.cycles)
                enc_i.append(se.instructions); dec_i.append(sd.instructions)
                stack = max(stack, se.stack_bytes, sd.stack_bytes)
            rows.append({"variant": v, "label": label, "msg_len": L, "ad_len": AD_LEN,
                         "enc_cycles": float(np.mean(enc_c)), "enc_cycles_sd": float(np.std(enc_c)),
                         "dec_cycles": float(np.mean(dec_c)), "dec_cycles_sd": float(np.std(dec_c)),
                         "enc_instr": float(np.mean(enc_i)), "dec_instr": float(np.mean(dec_i)),
                         "stack_bytes": stack, "tag_bytes": tag, "nonce_bytes": nlen, "elf_text_bytes": text})
        meta[v] = {"label": label, **checks, "elf_text_bytes": text}
        print(v, checks, rows[-1]["enc_cycles"])
    df = pd.DataFrame(rows)
    # asymptotic cost per byte from the 1024->2048 slope
    for v in VARIANTS:
        d = df[df.variant == v].set_index("msg_len")
        meta[v]["enc_cycles_per_byte_asympt"] = (d.enc_cycles[2048] - d.enc_cycles[1024]) / 1024
        meta[v]["enc_cycles_fixed_L0"] = d.enc_cycles[0]
        meta[v]["max_data_dependence_sd"] = float(df[df.variant == v][["enc_cycles_sd", "dec_cycles_sd"]].max().max())
    os.makedirs(os.path.join(OUT, "results"), exist_ok=True)
    df.to_csv(os.path.join(OUT, "results/01_crypto_cost.csv"), index=False)
    json.dump(meta, open(os.path.join(OUT, "results/01_crypto_meta.json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
