"""Check the Haversine CLI or measure its end-to-end throughput."""

import argparse
import json
import math
from pathlib import Path
import re
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "part2" / "checks"
TARGET = ROOT / "build" / "part2" / "cargo"
SUFFIX = ".exe" if sys.platform == "win32" else ""
RADIUS = 6372.8


def run(*args):
    return subprocess.run(
        [str(arg) for arg in args], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=600,
    ).stdout


def build():
    print("Building release binaries...", flush=True)
    run("cargo", "build", "--release", "--manifest-path", "part2/Cargo.toml",
        "--bins", "--target-dir", TARGET)
    BUILD.mkdir(parents=True, exist_ok=True)


def binary(name):
    return TARGET / "release" / (name + SUFFIX)


def check(path, count, expected):
    start = time.perf_counter()
    output = run(binary("average"), path)
    elapsed = time.perf_counter() - start
    count_match = re.search(r"Pair count:\s*(\d+)", output)
    mean_match = re.search(r"Mean Haversine distance:\s*(\S+)\s+km", output)
    if not count_match or not mean_match:
        raise RuntimeError(f"Unrecognized average output:\n{output}")
    actual_count = int(count_match[1])
    actual = float(mean_match[1])
    if actual_count != count or not math.isfinite(actual) or not math.isclose(
        actual, expected, rel_tol=1e-10, abs_tol=1e-8
    ):
        raise RuntimeError(
            f"{path.name}: expected count={count}, mean={expected:.16g}; "
            f"got count={actual_count}, mean={actual:.16g}"
        )
    return elapsed


def generate(method, seed, count):
    print(f"Generating {method}: {count:,} pairs, seed {seed}...", flush=True)
    run(binary("generate"), method, seed, count, BUILD)
    stem = BUILD / f"data_{method}_{seed}_{count}"
    answers = stem.with_suffix(".f64")
    if answers.stat().st_size != 8 * (count + 1):
        raise RuntimeError("Unexpected reference answer file size")
    with answers.open("rb") as stream:
        stream.seek(-8, 2)
        expected, = struct.unpack("<d", stream.read(8))
    return stem.with_suffix(".json"), expected


def correctness():
    cases = [
        ("same_point", [12, 34, 12, 34], 0),
        ("quarter_equator", [0, 0, 90, 0], math.pi * RADIUS / 2),
        ("half_equator", [0, 0, 180, 0], math.pi * RADIUS),
    ]
    for name, coordinates, expected in cases:
        path = BUILD / f"{name}.json"
        pair = dict(zip(("x0", "y0", "x1", "y1"), coordinates))
        # Pretty-print to exercise whitespace between fields and delimiters.
        path.write_text(json.dumps({"pairs": [pair]}, indent=2), encoding="utf-8")
        check(path, 1, expected)
        print(f"PASS: {name}")
    for method in ("uniform", "cluster"):
        for count in (1, 65, 10000):
            path, expected = generate(method, 42, count)
            check(path, count, expected)
            print(f"PASS: {method}, {count:,} pairs (count and reference mean)")


def performance(count, repeats):
    path, expected = generate("cluster", 42, count)
    print("Warm-up and reference check...", flush=True)
    check(path, count, expected)
    samples = []
    for index in range(repeats):
        elapsed = check(path, count, expected)
        samples.append(elapsed)
        print(f"Run {index + 1}: {elapsed:.3f} s, {count / elapsed:,.0f} pairs/s", flush=True)
    median = statistics.median(samples)
    size = path.stat().st_size
    print(f"Input: {count:,} pairs, {size / 1e6:.1f} MB")
    print(f"Median: {median:.3f} s, {count / median:,.0f} pairs/s, {size / median / 1e6:.1f} MB/s")
    print("Release build; includes process startup, file reads, parsing, and math.")
    print("Build/generation excluded; warm-up performed; OS file cache may be warm.")


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("correctness", "performance"))
    parser.add_argument("--pairs", type=positive, default=1_000_000)
    parser.add_argument("--repeats", type=positive, default=3)
    args = parser.parse_args()
    try:
        build()
        if args.action == "correctness":
            correctness()
        else:
            performance(args.pairs, args.repeats)
    except subprocess.CalledProcessError as error:
        print(error.stdout or "", file=sys.stderr)
        print(error.stderr or "", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
