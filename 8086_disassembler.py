"""8086 disassembler exercise"""

import argparse
from pathlib import Path
import sys


def get_register(*, w: int, reg: int) -> str:
    REGISTERS = (
        ("al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"),
        ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di"),
    )
    return REGISTERS[w][reg]


def decode_instruction(data: bytes, offset: int) -> tuple[str, int]:
    """Return (assembly instruction, number of bytes consumed).

    Start with register-to-register MOV for listings 0037 and 0038.
    Use the 8086 manual to identify the opcode, direction, width, and
    register fields. Reject unsupported encodings and truncated input
    with ValueError. Do not include 'bits 16' in the returned instruction.

    Example result shape: ("mov cx, bx", 2).
    """
    consumed_bytes = 0
    def munch(instr: str = "instruction") -> int:
        nonlocal consumed_bytes
        if offset + consumed_bytes >= len(data):
            raise ValueError(f"Truncated {instr} at {offset:#x}")
        consumed_bytes += 1
        return data[offset + consumed_bytes - 1]


    def munch_direct_address(instr: str) -> int:
        return munch(f"{instr}-lo") + (munch(f"{instr}-hi") << 8)


    def munch_mod_reg_r_m(instr: str) -> tuple[int, int, int]:
        byte1 = munch(instr)
        mod = (byte1 & 0b1100_0000) >> 6
        reg = (byte1 & 0b0011_1000) >> 3
        r_m =  byte1 & 0b0000_0111
        return (mod, reg, r_m)

    
    def munch_register_memory_dst(*, w: int, mod: int, r_m: int) -> str:
        EFFECTIVE_ADDRESSES = ("bx + si", "bx + di", "bp + si", "bp + di", "si", "di", "bp", "bx")
        if mod == 0b11:
            # MOV register to/from register
            return get_register(w=w, reg=r_m)
        else:
            # MOV register to/from memory
            if mod == 0b00 and r_m == 0b110:
                # DIRECT ADDRESS mode
                dst = munch_direct_address("MOV disp")
            else:
                dst = EFFECTIVE_ADDRESSES[r_m]
                displacement = 0
                if mod >= 0b01:
                    displacement += munch("MOV disp-lo")
                if mod == 0b10:
                    displacement += (munch("MOV disp-hi") << 8)

                # Two's complement sign correction for one-byte and two-byte displacements
                if mod == 0b01 and displacement >= (1 << 7):
                    displacement -= (1 << 8)
                if mod == 0b10 and displacement >= (1 << 15):
                    displacement -= (1 << 16)

                if displacement > 0:
                    dst = f"{dst} + {displacement}"
                elif displacement < 0:
                    dst = f"{dst} - {-displacement}"
            return f"[{dst}]"

    byte0 = munch()
    if (byte0 >> 2) == 0b10_0010:
        # MOV register/memory to/from register

        d = byte0 & 0b0000_0010
        w = byte0 & 0b0000_0001

        mod, reg, r_m = munch_mod_reg_r_m("MOV register/memory to/from register")

        dst = munch_register_memory_dst(w=w, mod=mod, r_m=r_m)
        src = get_register(w=w, reg=reg)

        if d:
            src, dst = dst, src
        return (f"mov {dst}, {src}", consumed_bytes)
        

    elif (byte0 >> 1) == 0b110_0011:
        # MOV immediate to register/memory
        w = byte0 & 0b0000_0001

        mod, reg, r_m = munch_mod_reg_r_m("MOV immediate to register/memory")
        assert reg == 0

        dst = munch_register_memory_dst(w=w, mod=mod, r_m=r_m)
        src = munch("MOV immediate to register/memory src")
        if w:
            src += munch("MOV immediate to register/memory data hi") << 8
        src_size = "word" if w else "byte"
        return (f"mov {dst}, {src_size} {src}", consumed_bytes)
    elif (byte0 >> 4) == 0b1011:
        # MOV immediate to register
        w =  (byte0 & 0b0000_1000) >> 3
        reg = byte0 & 0b0000_0111
        src = munch("MOV immediate to register lo")
        if w:
            src += munch("MOV immediate to register hi") << 8
        dst = get_register(w=w, reg=reg)
        return (f"mov {dst}, {src}", consumed_bytes)
    elif (byte0 >> 1) == 0b101_0000:
        # MOV memory to accumulator
        w = byte0 & 0b0000_0001
        src = f"[{munch_direct_address("MOV memory to accumulator addr")}]"
        dst = "ax" if w else "al"
        return (f"mov {dst}, {src}", consumed_bytes)
    elif (byte0 >> 1) == 0b1010001:
        # MOV accumulator to memory
        w = byte0 & 0b0000_0001
        src = "ax" if w else "al"
        dst = f"[{munch_direct_address("MOV accumulator to memory addr")}]"
        return (f"mov {dst}, {src}", consumed_bytes)

    elif (byte0 >> 1) == 0b1000_1110:
        # Register/memory to segment register
        raise NotImplementedError("MOV register/memory to segment register")
    elif byte0 == 0b1000_1100:
        # Segment register to register/memory
        raise NotImplementedError("MOV segment register to register/memory")

    raise NotImplementedError(f"Unimplemented instruction: {byte0:#b}")


def disassemble(data: bytes) -> str:
    lines = ["bits 16"]
    offset = 0
    while offset < len(data):
        instruction, size = decode_instruction(data, offset)
        if size <= 0 or offset + size > len(data):
            raise ValueError(f"Invalid instruction length {size!r} at {offset:#x}")
        lines.append(instruction)
        offset += size
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_binary", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Write assembly to a file")
    args = parser.parse_args()
    try:
        assembly = disassemble(args.input_binary.read_bytes())
        if args.output:
            args.output.write_text(assembly, encoding="utf-8")
        else:
            sys.stdout.write(assembly)
    except (OSError, ValueError, NotImplementedError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
