/* harness.c - common benchmark harness for all AEAD variants.
 * The host emulator (flora/m4emu.py) writes K, N, AD, M, g_mlen, g_adlen
 * then calls bench_enc() or bench_dec(); results are read back from C/P. */
#include <stdint.h>
#include <string.h>
#include "aead_iface.h"

#define MAXMSG 4096
uint8_t K[32]  __attribute__((aligned(8)));
uint8_t N[16]  __attribute__((aligned(8)));
uint8_t AD[64] __attribute__((aligned(8)));
uint8_t M[MAXMSG] __attribute__((aligned(8)));
uint8_t C[MAXMSG + 64] __attribute__((aligned(8)));
uint8_t P[MAXMSG] __attribute__((aligned(8)));
volatile uint32_t g_mlen, g_adlen, g_clen;
volatile int32_t g_ret;
const uint32_t g_taglen = AEAD_TAGLEN;
const uint32_t g_noncelen = AEAD_NONCELEN;

int bench_enc(void) {
  g_ret = aead_enc(C, M, g_mlen, AD, g_adlen, N, K);
  g_clen = g_mlen + AEAD_TAGLEN;
  return g_ret;
}
int bench_dec(void) {
  g_ret = aead_dec(P, C, g_clen, AD, g_adlen, N, K);
  return g_ret;
}
void bench_stop(void) { for (;;) { } }
