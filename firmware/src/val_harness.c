/* val_harness.c - reproduces the published Arduino Due (Cortex-M3) benchmark
 * set of the lwc-finalists library (ChaChaPoly units) for cycle-model validation. */
#include <stddef.h>
#include <stdint.h>
#include "aesgcm-aead.h"
#include "ascon-aead.h"
#include "elephant-delirium.h"
#include "elephant-dumbo.h"
#include "elephant-jumbo.h"
#include "gift-cofb-aead.h"
#include "grain-aead.h"
#include "internal-chachapoly.h"
#include "isap-a-aead.h"
#include "isap-k-aead.h"
#include "photon-beetle-aead.h"
#include "romulus-m-aead.h"
#include "romulus-n-aead.h"
#include "romulus-t-aead.h"
#include "sparkle-aead.h"
#include "tinyjambu-aead.h"
#include "xoodyak-aead.h"
typedef int (*enc_t)(unsigned char *, size_t *, const unsigned char *, size_t,
                     const unsigned char *, size_t, const unsigned char *, const unsigned char *);
typedef int (*dec_t)(unsigned char *, size_t *, const unsigned char *, size_t,
                     const unsigned char *, size_t, const unsigned char *, const unsigned char *);
#define A(n) {n##_aead_encrypt, n##_aead_decrypt}
const struct { enc_t e; dec_t d; } ALGS[] = {
  A(internal_chachapoly), A(schwaemm_128_128), A(xoodyak), A(schwaemm_256_128), A(schwaemm_192_192),
  A(ascon128a), A(ascon128), A(ascon80pq), A(schwaemm_256_256), A(tiny_jambu_128), A(gift_cofb),
  A(tiny_jambu_192), A(tiny_jambu_256), A(grain128), A(aesgcm128), A(aesgcm192), A(aesgcm256),
  A(romulus_n), A(delirium), A(photon_beetle_128), A(romulus_m), A(isap_ascon_128a), A(romulus_t),
  A(photon_beetle_32), A(isap_ascon_128), A(isap_keccak_128a), A(dumbo), A(jumbo), A(isap_keccak_128)};
uint8_t K[32], N[32], M[256], C[512], P[256];
volatile uint32_t g_alg, g_mlen, g_clen; volatile int32_t g_ret;
int bench_enc(void) { size_t cl; g_ret = ALGS[g_alg].e(C, &cl, M, g_mlen, 0, 0, N, K); g_clen = cl; return g_ret; }
int bench_dec(void) { size_t ml; g_ret = ALGS[g_alg].d(P, &ml, C, g_clen, 0, 0, N, K); return g_ret; }
void bench_stop(void) { for (;;) { } }
