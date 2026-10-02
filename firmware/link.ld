/* Flat memory map close to nRF52840: 1 MB flash at 0x0, 256 KB RAM at 0x20000000.
 * The emulator loads every PT_LOAD segment at its VMA, so no startup code. */
MEMORY { FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 1M
         RAM (rwx)  : ORIGIN = 0x20000000, LENGTH = 256K }
ENTRY(bench_enc)
SECTIONS {
  .text : { KEEP(*(.text.bench_*)) *(.text*) *(.rodata*) } > FLASH
  .data : { *(.data*) } > RAM
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) }
}
