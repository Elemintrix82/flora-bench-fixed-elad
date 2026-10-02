#ifndef AEAD_IFACE_H
#define AEAD_IFACE_H
#include <stdint.h>
/* Common interface: c = ciphertext || tag (tag length AEAD_TAGLEN).
 * aead_dec returns 0 on success, non-zero if authentication fails. */
int aead_enc(uint8_t *c, const uint8_t *m, uint32_t mlen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k);
int aead_dec(uint8_t *m, const uint8_t *c, uint32_t clen, const uint8_t *ad,
             uint32_t adlen, const uint8_t *n, const uint8_t *k);
#endif
