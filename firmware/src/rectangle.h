#ifndef RECTANGLE_H
#define RECTANGLE_H
#include <stdint.h>
#define RECTANGLE_RK_BYTES 208
void rectangle_key_schedule(const uint8_t *key, uint8_t *roundKeys);
void rectangle_encrypt(uint8_t *block, const uint8_t *roundKeys);
#endif
