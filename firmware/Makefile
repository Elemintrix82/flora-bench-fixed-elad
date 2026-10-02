# Builds one bare-metal ELF per AEAD variant for Cortex-M4 (and M3 for validation).
CC = arm-none-eabi-gcc
OPT ?= -O2
CPU ?= cortex-m4
OUT ?= build/$(CPU)$(OPT)
TP = third_party
CFLAGS = -mcpu=$(CPU) -mthumb -mfloat-abi=soft $(OPT) -ffunction-sections -fdata-sections \
         -fno-common -Wall -Wno-unused-function -Isrc
LDFLAGS = -T link.ld -nostartfiles --specs=nano.specs -Wl,--gc-sections -Wl,--no-warn-rwx-segments
LWC = $(TP)/lwc
VARIANTS = ascon_armv7m ascon_ref aesgcm chacha20poly1305 giftcofb xoodyak rectangle_ctr_hmac lwcchachapoly
all: $(addprefix $(OUT)/,$(addsuffix .elf,$(VARIANTS)))
$(OUT):
	mkdir -p $(OUT)
$(OUT)/ascon_armv7m.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=16 -DAEAD_NONCELEN=16 -I$(TP)/ascon_armv7m -I$(TP) src/harness.c src/wrap_ascon.c $(TP)/ascon_armv7m/aead.c $(TP)/ascon_armv7m/permutations.c $(LDFLAGS) -o $@
$(OUT)/ascon_ref.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=16 -DAEAD_NONCELEN=16 -I$(TP)/ascon_ref -I$(TP) src/harness.c src/wrap_ascon.c $(TP)/ascon_ref/aead.c $(LDFLAGS) -o $@
$(OUT)/aesgcm.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=16 -DAEAD_NONCELEN=12 -I$(LWC) src/harness.c src/wrap_aesgcm.c $(LWC)/aesgcm-aead.c $(LWC)/internal-aes.c $(LWC)/internal-ghash.c $(LWC)/internal-util.c $(LDFLAGS) -o $@
$(OUT)/chacha20poly1305.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=16 -DAEAD_NONCELEN=12 -I$(TP)/monocypher src/harness.c src/wrap_chacha20poly1305.c $(TP)/monocypher/monocypher.c $(LDFLAGS) -o $@
$(OUT)/giftcofb.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=16 -DAEAD_NONCELEN=16 -I$(LWC) src/harness.c src/wrap_giftcofb.c $(LWC)/gift-cofb-aead.c $(LWC)/internal-gift128.c $(LWC)/internal-gift128b-full-armv7m.S $(LWC)/internal-util.c $(LDFLAGS) -o $@
$(OUT)/xoodyak.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=16 -DAEAD_NONCELEN=16 -I$(LWC) src/harness.c src/wrap_xoodyak.c $(LWC)/xoodyak-aead.c $(LWC)/internal-xoodoo.c $(LWC)/internal-xoodoo-armv7m.S $(LWC)/internal-util.c $(LDFLAGS) -o $@
$(OUT)/rectangle_ctr_hmac.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=32 -DAEAD_NONCELEN=4 -I$(LWC) src/harness.c src/wrap_rectangle_ctr_hmac.c src/rectangle.c $(LWC)/internal-sha256.c $(LWC)/internal-sha256-armv7m.S $(LWC)/internal-util.c $(LDFLAGS) -o $@
$(OUT)/lwcchachapoly.elf: | $(OUT)
	$(CC) $(CFLAGS) -DAEAD_TAGLEN=16 -DAEAD_NONCELEN=16 -I$(LWC) src/harness.c src/wrap_lwcchachapoly.c $(LWC)/internal-chachapoly.c $(LWC)/internal-util.c $(LDFLAGS) -o $@
clean:
	rm -rf build
