#include "aead_iface.h"
#include "crypto_aead.h"
int aead_enc(uint8_t *c, const uint8_t *m, uint32_t mlen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  unsigned long long clen;
  return crypto_aead_encrypt(c, &clen, m, mlen, ad, adlen, 0, n, k);
}
int aead_dec(uint8_t *m, const uint8_t *c, uint32_t clen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  unsigned long long mlen;
  return crypto_aead_decrypt(m, &mlen, 0, c, clen, ad, adlen, n, k);
}
