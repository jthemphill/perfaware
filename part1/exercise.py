"""Assemble, run, and check the part 1 disassembler exercises."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "part1"
DISASSEMBLER = ROOT / "part1" / "8086_disassembler.py"
INPUTS = ROOT / "vendor" / "computer_enhance" / "perfaware" / "part1"
SUPPORTED_LISTINGS = {"0037", "0038", "0039", "0040", "0041"}


def nasm() -> str:
    local = ROOT / ".tools" / "nasm-3.02" / "nasm.exe"
    found = str(local) if local.exists() else shutil.which("nasm")
    if not found:
        raise RuntimeError("NASM missing. See README.md for setup.")
    return found


def run(*args: str | Path) -> None:
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def assemble(source: Path) -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)
    binary = BUILD / (source.stem + ".bin")
    run(nasm(), "-f", "bin", source, "-o", binary)
    return binary


def check(source: Path, binary: Path) -> None:
    output = BUILD / (source.stem + ".decoded.asm")
    run(sys.executable, DISASSEMBLER, binary, "-o", output)
    rebuilt = BUILD / (source.stem + ".roundtrip.bin")
    run(nasm(), "-f", "bin", output, "-o", rebuilt)
    if binary.read_bytes() != rebuilt.read_bytes():
        raise RuntimeError(f"Round-trip bytes differ: {source.name}")
    print(f"PASS: {source.name} (round-trip bytes identical)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["assemble", "run", "check", "bytes"])
    parser.add_argument("listing", nargs="?", default="supported",
                        help="Listing number, supported (default), or all upstream part1 listings")
    args = parser.parse_args()
    if not INPUTS.is_dir():
        parser.error("Course listings missing. Run: git submodule update --init --recursive")
    sources = sorted(INPUTS.glob("listing_*.asm"))
    if args.listing == "supported":
        sources = [s for s in sources if s.name.split("_")[1] in SUPPORTED_LISTINGS]
    elif args.listing != "all":
        sources = [s for s in sources if s.name.startswith(f"listing_{args.listing}_")]
    if not sources:
        parser.error(f"No listings found for {args.listing!r}")
    failed = False
    for source in sources:
        try:
            binary = assemble(source)
            if args.action == "run":
                run(sys.executable, DISASSEMBLER, binary)
            elif args.action == "check":
                check(source, binary)
            elif args.action == "bytes":
                print(source.name)
                for offset, byte in enumerate(binary.read_bytes()):
                    print(f"{offset:04x}: {byte:02x}  {byte:08b}")
            else:
                print(f"Assembled {binary.relative_to(ROOT)}")
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"FAIL: {source.name}: {error}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
