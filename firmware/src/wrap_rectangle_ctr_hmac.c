/* Configuration used for HIGH data in Elad et al. (JIS 2026):
 * RECTANGLE-64/128 in CTR mode + HMAC-SHA256 (encrypt-then-MAC).
 * Counter block = nonce (32 bits) || block counter (32 bits), as a 96-bit
 * nonce cannot fit a 64-bit block. MAC over AD || nonce || ciphertext,
 * full 32-byte tag. Encryption key = k[0..15], MAC key = k[16..31].
 * The key schedule is executed for each message (no pre-computed state). */
#include <string.h>
#include "aead_iface.h"
#include "rectangle.h"
#include "internal-sha256.h"

static void ctr_xor(uint8_t *out, const uint8_t *in, uint32_t len,
                    const uint8_t *n, const uint8_t *rk) {
  uint8_t blk[8]; uint32_t ctr = 0, i, j;
  for (i = 0; i < len; i += 8) {
    memcpy(blk, n, 4);
    blk[4] = (uint8_t)ctr; blk[5] = (uint8_t)(ctr >> 8);
    blk[6] = (uint8_t)(ctr >> 16); blk[7] = (uint8_t)(ctr >> 24);
    rectangle_encrypt(blk, rk);
    for (j = 0; j < 8 && i + j < len; j++) out[i + j] = in[i + j] ^ blk[j];
    ctr++;
  }
}
static void mac(uint8_t *tag, const uint8_t *ad, uint32_t adlen, const uint8_t *n,
                const uint8_t *c, uint32_t clen, const uint8_t *mk) {
  sha256_state_t st;
  internal_sha256_hmac_init(&st, mk, 16);
  internal_sha256_hmac_update(&st, ad, adlen);
  internal_sha256_hmac_update(&st, n, 4);
  internal_sha256_hmac_update(&st, c, clen);
  internal_sha256_hmac_finalize(&st, mk, 16, tag);
}
int aead_enc(uint8_t *c, const uint8_t *m, uint32_t mlen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  uint8_t rk[RECTANGLE_RK_BYTES] __attribute__((aligned(4)));
  rectangle_key_schedule(k, rk);
  ctr_xor(c, m, mlen, n, rk);
  mac(c + mlen, ad, adlen, n, c, mlen, k + 16);
  return 0;
}
int aead_dec(uint8_t *m, const uint8_t *c, uint32_t clen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  uint8_t rk[RECTANGLE_RK_BYTES] __attribute__((aligned(4))); uint8_t t[32];
  uint32_t mlen = clen - 32, i; uint8_t d = 0;
  mac(t, ad, adlen, n, c, mlen, k + 16);
  for (i = 0; i < 32; i++) d |= t[i] ^ c[mlen + i];
  if (d) return -1;
  rectangle_key_schedule(k, rk);
  ctr_xor(m, c, mlen, n, rk);
  return 0;
}
/* single-block entry used for the FELICS test vector */
void rect_block_test(uint8_t *blk, const uint8_t *key) {
  uint8_t rk[RECTANGLE_RK_BYTES] __attribute__((aligned(4)));
  rectangle_key_schedule(key, rk); rectangle_encrypt(blk, rk);
}
