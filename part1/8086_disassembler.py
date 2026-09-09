"""8086 disassembler exercise"""

import argparse
from pathlib import Path
import sys


def get_size(w: int) -> str:
    return "word" if w else "byte"


def get_register(*, w: int, reg: int) -> str:
    REGISTERS = (
        ("al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"),
        ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di"),
    )
    return REGISTERS[w][reg]

ARITH_OPCODES = ("add", "or", "adc", "sbb", "and", "sub", "xor", "cmp")

LOOP_OPCODES = ("loopnz", "loopz", "loop", "jcxz")

# Indexed by the low nibble of opcodes 0x70 through 0x7F.
JUMP_OPCODES = (
    "jo", "jno", "jb", "jae",
    "je", "jne", "jbe", "ja",
    "js", "jns", "jp", "jnp",
    "jl", "jge", "jle", "jg",
)

def decode_instruction(data: bytes, offset: int) -> tuple[str, int]:
    """Return (assembly instruction, number of bytes consumed).

    Start with register-to-register MOV for listings 0037 and 0038.
    Use the 8086 manual to identify the opcode, direction, width, and
    register fields. Reject unsupported encodings and truncated input
    with ValueError. Do not include 'bits 16' in the returned instruction.

    Example result shape: ("mov cx, bx", 2).
    """
    consumed_bytes = 0
    def munch(instr: str) -> int:
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

    
    def munch_register_memory_dst(instr, *, w: int, mod: int, r_m: int) -> str:
        EFFECTIVE_ADDRESSES = ("bx + si", "bx + di", "bp + si", "bp + di", "si", "di", "bp", "bx")
        if mod == 0b11:
            # MOV register to/from register
            return get_register(w=w, reg=r_m)
        else:
            # MOV register to/from memory
            if mod == 0b00 and r_m == 0b110:
                # DIRECT ADDRESS mode
                dst = munch_direct_address(f"{instr} direct address")
            else:
                dst = EFFECTIVE_ADDRESSES[r_m]
                displacement = 0
                if mod >= 0b01:
                    displacement += munch(f"{instr} disp-lo")
                if mod == 0b10:
                    displacement += (munch(f"{instr} disp-hi") << 8)

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

    def munch_immediate(instr: str, *, w: int, s: int) -> int:
        src = munch(f"{instr}-lo")
        if w and not s:
            src += munch(f"{instr}-hi") << 8
        elif w and s and src >= (1 << 7):
            src -= (1 << 8)
        return src

    byte0 = munch("Initial opcode")
    if (byte0 & 0b1111_1100) == 0b1000_1000:
        # MOV register/memory to/from register

        d = byte0 & 0b0000_0010
        w = byte0 & 0b0000_0001

        mod, reg, r_m = munch_mod_reg_r_m("MOV register/memory to/from register")

        dst = munch_register_memory_dst("MOV register/memory to/from register", w=w, mod=mod, r_m=r_m)
        src = get_register(w=w, reg=reg)

        if d:
            src, dst = dst, src
        return (f"mov {dst}, {src}", consumed_bytes)
        

    elif (byte0 & 0b1111_1110) == 0b1100_0110:
        # MOV immediate to register/memory
        w = byte0 & 0b0000_0001

        mod, reg, r_m = munch_mod_reg_r_m("MOV immediate to register/memory")
        assert reg == 0

        dst = munch_register_memory_dst("MOV register/memory to/from register", w=w, mod=mod, r_m=r_m)
        src = munch_immediate("MOV immediate to register/memory src", w=w, s=0)
        src_size = get_size(w)
        return (f"mov {dst}, {src_size} {src}", consumed_bytes)
    elif (byte0 & 0b1111_0000) == 0b1011_0000:
        # MOV immediate to register
        w =  (byte0 & 0b0000_1000) >> 3
        reg = byte0 & 0b0000_0111
        src = munch("MOV immediate to register lo")
        if w:
            src += munch("MOV immediate to register hi") << 8
        dst = get_register(w=w, reg=reg)
        return (f"mov {dst}, {src}", consumed_bytes)
    elif (byte0 & 0b1111_1110) == 0b1010_0000:
        # MOV memory to accumulator
        w = byte0 & 0b0000_0001
        src = f"[{munch_direct_address('MOV memory to accumulator addr')}]"
        dst = "ax" if w else "al"
        return (f"mov {dst}, {src}", consumed_bytes)
    elif (byte0 & 0b1111_1110) == 0b1010_0010:
        # MOV accumulator to memory
        w = byte0 & 0b0000_0001
        src = "ax" if w else "al"
        dst = f"[{munch_direct_address('MOV accumulator to memory addr')}]"
        return (f"mov {dst}, {src}", consumed_bytes)
    elif (byte0 & 0b1111_1111) == 0b1000_1110:
        # MOV register/memory to segment register
        raise NotImplementedError("MOV register/memory to segment register")
    elif (byte0 & 0b1111_1111) == 0b1000_1100:
        # MOV segment register to register/memory
        raise NotImplementedError("MOV segment register to register/memory")
    elif (byte0 & 0b1100_0100) == 0b0000_0000:
        # Arithmetic reg/memory with register to either
        d = (byte0 & 0b0000_0010) >> 1
        w =  byte0 & 0b0000_0001
        mod, reg, r_m = munch_mod_reg_r_m("Arithmetic reg/memory with register to either")
        opcode = ARITH_OPCODES[(byte0 & 0b0011_1000) >> 3]
        dst = munch_register_memory_dst("Arithmetic reg/memory with register to either", w=w, mod=mod, r_m=r_m)
        src = get_register(w=w, reg=reg)
        if d:
            src, dst = dst, src
        return (f"{opcode} {dst}, {src}", consumed_bytes)

    elif (byte0 & 0b1111_1100) == 0b1000_0000:
        # Arithmetic immediate to register/memory
        s = (byte0 & 0b0000_0010) >> 1
        w =  byte0 & 0b0000_0001
        mod, reg, r_m = munch_mod_reg_r_m("Arithmetic immediate to register/memory")
        opcode = ARITH_OPCODES[reg]
        dst = munch_register_memory_dst("Arithmetic immediate to register/memory", w=w, mod=mod, r_m=r_m)
        if mod != 0b11:
            dst = f"{get_size(w)} {dst}"
        src = munch_immediate("Arithmetic immediate to register/memory", w=w, s=s)
        return (f"{opcode} {dst}, {src}", consumed_bytes)

    elif (byte0 & 0b1100_0110) == 0b0000_0100:
        # Arithmetic immediate to accumulator
        w = byte0 & 0b0000_0001
        src = munch_immediate("Arithmetic immediate to accumulator", w=w, s=0)
        opcode = ARITH_OPCODES[(byte0 & 0b0011_1000) >> 3]
        dst = "ax" if w else "al"
        return (f"{opcode} {dst}, {src}", consumed_bytes)

    elif (byte0 & 0b1111_0000) == 0b0111_0000:
        # Conditional jump
        opcode = JUMP_OPCODES[byte0 & 0b0000_1111]
    elif (byte0 & 0b1111_1100) == 0b1110_0000:
        # loop
        opcode = LOOP_OPCODES[byte0 & 0b11]
    else:
        raise NotImplementedError(f"Unimplemented instruction: {byte0:#b}")
    displacement = munch_immediate(f"{opcode} ip-inc8", w=1, s=1)
    target = consumed_bytes + displacement
    return (f"{opcode} ${target:+d}", consumed_bytes)



def disassemble(data: bytes) -> str:
    lines = ["bits 16"]
    offset = 0
    while offset < len(data):
        instruction, size = decode_instruction(data, offset)
        if size <= 0 or offset + size > len(data):
            raise ValueError(f"Invalid instruction length {size!r} at {offset:#x}")
        lines.append(instruction)
        print(instruction)
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
