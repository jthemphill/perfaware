"""Build an instrumented debugger executable and generate exactly one pair."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Optimize while retaining debug symbols")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    target = root / "build/part2/debugger"
    environment = os.environ.copy()
    environment["CARGO_PROFILE_DEV_DEBUG"] = "2"
    environment["CARGO_PROFILE_RELEASE_DEBUG"] = "2"
    command = ["cargo", "build", "--locked", "--manifest-path", "part2/Cargo.toml",
               "--bins", "--no-default-features", "--features", "profiling",
               "--target-dir", str(target)]
    if args.release:
        command.append("--release")
    subprocess.run(command, cwd=root, env=environment, check=True)
    profile = "release" if args.release else "debug"
    suffix = ".exe" if sys.platform == "win32" else ""
    subprocess.run([str(target / profile / ("generate" + suffix)), "cluster", "42", "1",
                    str(target / "input")], cwd=root, check=True)
    print(f"Ready to debug {target / profile / ('average' + suffix)} with one pair.")


if __name__ == "__main__":
    main()
