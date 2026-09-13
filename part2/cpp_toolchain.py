"""Find a native C++ compiler in the configured environment."""

import os
import shutil
import sys


def find_compiler():
    override = os.environ.get("CXX")
    if override:
        return override
    candidates = ("cl", "clang-cl", "clang++", "g++") if sys.platform == "win32" else ("clang++", "g++")
    for name in candidates:
        compiler = shutil.which(name)
        if compiler:
            return compiler
    if sys.platform == "win32":
        raise RuntimeError("No C++ compiler found. Launch VS Code in a Developer environment "
                           "or run from a Developer terminal with the C++ toolchain installed; "
                           "CXX can select a compiler executable.")
    raise RuntimeError("Install a C++ compiler (macOS: xcode-select --install) or set CXX to its executable.")
