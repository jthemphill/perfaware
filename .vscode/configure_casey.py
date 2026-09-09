"""Generate a local IntelliSense database for Casey's unity-build listings."""

import json
import os
from pathlib import Path
import re
import shutil
import sys


def main():
    root = Path(__file__).resolve().parent.parent
    source = root / "vendor/computer_enhance/perfaware"
    # Included .cpp fragments must not be separate translation units: their
    # typedefs, macros, and dependencies come from the including main listing.
    mains = [path for path in sorted(source.glob("part*/listing_*.cpp"))
             if re.search(r"^\s*int\s+main\s*\(", path.read_text(), re.MULTILINE)]
    if not mains:
        sys.exit("Initialize the course source: git submodule update --init --recursive")

    candidates = ("cl", "clang-cl", "clang++", "g++") if sys.platform == "win32" else ("clang++", "g++")
    compiler = os.environ.get("CXX") or next(
        (found for name in candidates if (found := shutil.which(name))), None)
    if not compiler:
        sys.exit("Install a C++ compiler or set CXX to its executable. For MSVC, use a Developer terminal.")
    compiler = shutil.which(compiler) or compiler
    msvc = Path(compiler).stem.lower() in ("cl", "clang-cl")
    flags = ["/std:c++17", "/arch:AVX2", "/EHsc", "/c"] if msvc else ["-std=c++17", "-mavx2", "-c"]
    if sys.platform == "darwin":
        # The course's RDTSC/AVX code targets x86 even on Apple Silicon.
        # These are editor parsing flags, not changes to the benchmark build.
        flags += ["-arch", "x86_64"]

    entries = [{"directory": str(path.parent), "file": str(path),
                "arguments": [compiler, *flags, str(path)]} for path in mains]
    output = root / "build/casey-intellisense/compile_commands.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"Configured {len(entries)} main listings using {compiler}.")
    print(f"IntelliSense database: {output}")


if __name__ == "__main__":
    main()
