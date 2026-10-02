/* RECTANGLE-64/128 block cipher (Zhang et al., Sci. China Inf. Sci. 2015).
 * Derived from the FELICS "RECTANGLE_64_128_v04" optimised C implementation
 * (32-bit branch, authors of RECTANGLE / University of Luxembourg, GPLv3);
 * FELICS macros replaced by plain memory accesses. */
#include <stdint.h>
#include <string.h>
#include "rectangle.h"

static const uint8_t RC[25] = {
  0x01, 0x02, 0x04, 0x09, 0x12, 0x05, 0x0b, 0x16, 0x0c, 0x19, 0x13, 0x07,
  0x0f, 0x1f, 0x1e, 0x1c, 0x18, 0x11, 0x03, 0x06, 0x0d, 0x1b, 0x17, 0x0e, 0x1d};

void rectangle_key_schedule(const uint8_t *key, uint8_t *roundKeys) {
  uint32_t key32[4]; uint8_t *key8 = (uint8_t *)key32;
  uint16_t *key16 = (uint16_t *)key32; uint16_t *rk16 = (uint16_t *)roundKeys;
  uint8_t i, sbox0, sbox1; uint16_t halfRow2; uint32_t tempRow0;
  memcpy(key32, key, 16);
  rk16[0] = key16[0]; rk16[1] = key16[2]; rk16[2] = key16[4]; rk16[3] = key16[6];
  for (i = 1; i <= 25; i++) {
    sbox1 = ~key8[4]; sbox0 = sbox1 | key8[12]; sbox0 ^= key8[0];
    key8[0] &= sbox1; sbox1 = key8[8] ^ key8[12]; key8[0] ^= sbox1;
    key8[12] = key8[4] ^ key8[8]; key8[4] = key8[8] ^ sbox0;
    sbox1 &= sbox0; key8[12] ^= sbox1; key8[8] = key8[0] | key8[12]; key8[8] ^= sbox0;
    tempRow0 = key32[0];
    key32[0] = (tempRow0 << 8 | tempRow0 >> 24) ^ key32[1];
    key32[1] = key32[2];
    halfRow2 = key16[4];
    key16[4] = key16[5] ^ key16[6];
    key16[5] = halfRow2 ^ key16[7];
    key32[3] = tempRow0;
    key8[0] ^= RC[i - 1];
    rk16[4 * i] = key16[0]; rk16[4 * i + 1] = key16[2];
    rk16[4 * i + 2] = key16[4]; rk16[4 * i + 3] = key16[6];
  }
}

void rectangle_encrypt(uint8_t *block, const uint8_t *roundKeys) {
  uint32_t b32[2], temprk; const uint32_t *rk32 = (const uint32_t *)roundKeys;
  uint16_t w0, w1, w2, w3, sbox0, sbox1; uint8_t i;
  memcpy(b32, block, 8);
  w0 = (uint16_t)b32[0]; w1 = (uint16_t)(b32[0] >> 16);
  w2 = (uint16_t)b32[1]; w3 = (uint16_t)(b32[1] >> 16);
  for (i = 0; i < 25; i++) {
    temprk = *rk32++; w0 ^= (uint16_t)temprk; w1 ^= (uint16_t)(temprk >> 16);
    temprk = *rk32++; w2 ^= (uint16_t)temprk; w3 ^= (uint16_t)(temprk >> 16);
    sbox1 = ~w1; sbox0 = sbox1 | w3; sbox0 ^= w0; w0 &= sbox1;
    sbox1 = w2 ^ w3; w0 ^= sbox1; w3 = w1 ^ w2; w1 = w2 ^ sbox0;
    sbox1 &= sbox0; w3 ^= sbox1; w2 = w0 | w3; w2 ^= sbox0;
    w1 = (uint16_t)(w1 << 1 | w1 >> 15);
    w2 = (uint16_t)(w2 << 12 | w2 >> 4);
    w3 = (uint16_t)(w3 << 13 | w3 >> 3);
  }
  temprk = *rk32++; w0 ^= (uint16_t)temprk; w1 ^= (uint16_t)(temprk >> 16);
  temprk = *rk32++; w2 ^= (uint16_t)temprk; w3 ^= (uint16_t)(temprk >> 16);
  b32[0] = ((uint32_t)w1 << 16) + w0; b32[1] = ((uint32_t)w3 << 16) + w2;
  memcpy(block, b32, 8);
}
