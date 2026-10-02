"""m4emu.py - Cortex-M3/M4 instruction-level emulator with a cycle model.

Executes a bare-metal ELF (built by firmware/Makefile) with Unicorn and assigns
each executed instruction a cycle cost from the ARM Cortex-M4 Technical
Reference Manual (r0p1, section 3.3.1, Table 3-1) timing rules:
  * data processing, multiply (MUL, UMULL, SMULL, UMLAL, SMLAL): 1 cycle
  * MLA/MLS: 2 cycles; SDIV/UDIV: DIV_CYCLES (2..12 in the TRM)
  * single load/store: 2 cycles, 1 cycle when pipelined after a single load
  * LDRD/STRD: 3 cycles; LDM/STM/PUSH/POP: 1 + N registers
  * taken branch / write to PC: 1 + P, P = pipeline refill (1..3 in the TRM)
  * TBB/TBH: 2 + P; IT: 1 cycle (folding ignored, conservative)
Zero flash wait states are assumed (code served by the flash cache).
The output is therefore a model estimate of cycles; instruction counts are exact.
"""
from __future__ import annotations
import struct
from dataclasses import dataclass
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_PC
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_REG, ARM_REG_PC

FLASH_BASE, FLASH_SIZE = 0x00000000, 1 << 20
RAM_BASE, RAM_SIZE = 0x20000000, 256 << 10
STACK_TOP = RAM_BASE + RAM_SIZE - 16
P_REFILL = 2      # mid value of the TRM range 1..3
DIV_CYCLES = 7    # mid value of the TRM range 2..12

LOAD_SINGLE = {"ldr", "ldrb", "ldrh", "ldrsb", "ldrsh", "ldrex", "ldrexb", "ldrexh", "ldrt", "ldrbt", "ldrht"}
STORE_SINGLE = {"str", "strb", "strh", "strex", "strexb", "strexh", "strt", "strbt", "strht"}
BRANCHES = {"b", "bl", "bx", "blx", "cbz", "cbnz"}


def _base(mn: str) -> str:
    m = mn.split(".")[0]
    # strip condition codes / flag-setting suffix for classification
    for cc in ("eq", "ne", "cs", "hs", "cc", "lo", "mi", "pl", "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le", "al"):
        if m.endswith(cc) and m[:-2] in LOAD_SINGLE | STORE_SINGLE | BRANCHES | {"ldrd", "strd", "ldm", "stm", "pop", "push", "mov", "add"}:
            m = m[:-2]
            break
    return m


@dataclass
class RunStats:
    instructions: int
    cycles: int
    stack_bytes: int
    ret: int


class M4Emu:
    def __init__(self, elf_path: str):
        self.elf_path = elf_path
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            self.segments = [(s["p_vaddr"], s.data(), s["p_memsz"]) for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
            symtab = elf.get_section_by_name(".symtab")
            self.sym = {s.name: (s["st_value"], s["st_size"]) for s in symtab.iter_symbols() if s.name}
        self.cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
        self.cs.detail = True
        self._icache: dict[int, tuple[str, int, bool, int]] = {}
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.uc.mem_map(FLASH_BASE, FLASH_SIZE)
        self.uc.mem_map(RAM_BASE, RAM_SIZE)
        for vaddr, data, memsz in self.segments:
            self.uc.mem_write(vaddr, data + b"\x00" * (memsz - len(data)))
        self.stop_addr = self.sym["bench_stop"][0] & ~1
        self.uc.hook_add(UC_HOOK_CODE, self._hook)

    # ---- instruction classification (cached per address)
    def _decode(self, addr: int, size: int):
        code = bytes(self.uc.mem_read(addr, size))
        ins = next(self.cs.disasm(code, addr), None)
        if ins is None:
            return ("?", 1, False, 0)
        mn = _base(ins.mnemonic)
        writes_pc = False
        nregs = 0
        if mn in ("pop", "ldm", "ldmia", "ldmdb", "push", "stm", "stmia", "stmdb", "ldmfd", "stmfd"):
            regs = [op for op in ins.operands if op.type == ARM_OP_REG]
            nregs = len(regs) - (0 if mn in ("pop", "push") else 1)
            writes_pc = any(op.reg == ARM_REG_PC for op in regs) and mn.startswith(("pop", "ldm"))
        elif ins.operands and ins.operands[0].type == ARM_OP_REG and ins.operands[0].reg == ARM_REG_PC:
            writes_pc = mn not in STORE_SINGLE and mn not in ("cmp", "cmn", "tst", "teq")
        return (mn, size, writes_pc, nregs)

    def _hook(self, uc, addr, size, _):
        info = self._icache.get(addr)
        if info is None:
            info = self._decode(addr, size)
            self._icache[addr] = info
        # flow change of the previous instruction => taken branch penalty
        if self._prev_end is not None and addr != self._prev_end and self._prev_branchlike:
            self.cycles += P_REFILL
        mn, sz, writes_pc, nregs = info
        c = 1
        pipelined = False
        if mn in LOAD_SINGLE:
            c = 1 if self._prev_load else 2
            pipelined = True
        elif mn in STORE_SINGLE:
            c = 1 if self._prev_load else 2
        elif mn in ("ldrd", "strd"):
            c = 3
        elif mn in ("ldm", "ldmia", "ldmdb", "ldmfd", "stm", "stmia", "stmdb", "stmfd", "pop", "push"):
            c = 1 + nregs
        elif mn in ("mla", "mls"):
            c = 2
        elif mn in ("sdiv", "udiv"):
            c = DIV_CYCLES
        elif mn in ("tbb", "tbh"):
            c = 2
        self.cycles += c
        self.instructions += 1
        self._prev_load = pipelined
        self._prev_end = addr + sz
        self._prev_branchlike = (mn in BRANCHES) or writes_pc or mn in ("tbb", "tbh")
        sp = uc.reg_read(UC_ARM_REG_SP)
        if sp < self._min_sp:
            self._min_sp = sp

    # ---- memory helpers
    def write(self, name: str, data: bytes, offset: int = 0):
        self.uc.mem_write(self.sym[name][0] + offset, data)

    def read(self, name: str, n: int, offset: int = 0) -> bytes:
        return bytes(self.uc.mem_read(self.sym[name][0] + offset, n))

    def write_u32(self, name: str, v: int):
        self.write(name, struct.pack("<I", v & 0xFFFFFFFF))

    def read_u32(self, name: str) -> int:
        return struct.unpack("<I", self.read(name, 4))[0]

    def call(self, func: str, args: tuple[int, ...] = ()) -> RunStats:
        self.cycles = 0
        self.instructions = 0
        self._prev_load = False
        self._prev_end = None
        self._prev_branchlike = False
        self._min_sp = STACK_TOP
        self.uc.reg_write(UC_ARM_REG_SP, STACK_TOP)
        self.uc.reg_write(UC_ARM_REG_LR, self.stop_addr | 1)
        for i, a in enumerate(args):
            self.uc.reg_write(UC_ARM_REG_R0 + i, a)
        start = self.sym[func][0] | 1
        self.uc.emu_start(start, self.stop_addr, count=500_000_000)
        ret = self.uc.reg_read(UC_ARM_REG_R0)
        # the stop instruction itself is not counted (hook fires before stop? subtract if so)
        return RunStats(self.instructions, self.cycles, STACK_TOP - self._min_sp, ret)
