#include <string.h>
#include "aead_iface.h"
#include "monocypher.h"
int aead_enc(uint8_t *c, const uint8_t *m, uint32_t mlen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  crypto_aead_ctx ctx; uint8_t key[32];
  memcpy(key, k, 32);  /* ChaCha20 uses a 256-bit key */
  crypto_aead_init_ietf(&ctx, key, n);
  crypto_aead_write(&ctx, c, c + mlen, ad, adlen, m, mlen);
  return 0;
}
int aead_dec(uint8_t *m, const uint8_t *c, uint32_t clen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  crypto_aead_ctx ctx; uint8_t key[32]; uint32_t mlen = clen - 16;
  memcpy(key, k, 32);
  crypto_aead_init_ietf(&ctx, key, n);
  return crypto_aead_read(&ctx, m, c + mlen, ad, adlen, c, mlen);
}
