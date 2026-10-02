/* lwc-finalists ChaChaPoly: used ONLY to reproduce the "ChaChaPoly units" of the
 * published Arduino Due benchmark (cycle-model validation). Not RFC 8439. */
#include <stddef.h>
#include "aead_iface.h"
#include "internal-chachapoly.h"
int aead_enc(uint8_t *c, const uint8_t *m, uint32_t mlen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  size_t clen; return internal_chachapoly_aead_encrypt(c, &clen, m, mlen, ad, adlen, n, k);
}
int aead_dec(uint8_t *m, const uint8_t *c, uint32_t clen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k) {
  size_t mlen; return internal_chachapoly_aead_decrypt(m, &mlen, c, clen, ad, adlen, n, k);
}
