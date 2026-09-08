"""Check the Haversine CLI or measure its end-to-end throughput."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import statistics
import struct
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "part2" / "checks"
TARGET = ROOT / "build" / "part2" / "cargo"
SUFFIX = ".exe" if sys.platform == "win32" else ""
RADIUS = 6372.8


def run(*args, env=None):
    return subprocess.run(
        [str(arg) for arg in args], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=600, env=env,
    ).stdout


def build():
    print("Building release binaries...", flush=True)
    run("cargo", "build", "--release", "--manifest-path", "part2/Cargo.toml",
        "--bins", "--target-dir", TARGET)
    BUILD.mkdir(parents=True, exist_ok=True)


def binary(name):
    return TARGET / "release" / (name + SUFFIX)


def check(path, count, expected, trace=None):
    environment = os.environ.copy()
    environment.pop("HAVERSINE_TRACE", None)
    if trace is not None:
        environment["HAVERSINE_TRACE"] = str(trace)
    start = time.perf_counter()
    output = run(binary("average"), path, env=environment)
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


def generate(method, seed, count, regenerate=False):
    stem = BUILD / f"data_{method}_{seed}_{count}"
    pairs = stem.with_suffix(".json")
    answers = stem.with_suffix(".f64")
    reusable = (
        not regenerate
        and pairs.is_file() and pairs.stat().st_size > 0
        and answers.is_file() and answers.stat().st_size == 8 * (count + 1)
    )
    if reusable:
        with answers.open("rb") as stream:
            stream.seek(-8, 2)
            reusable = math.isfinite(struct.unpack("<d", stream.read(8))[0])
    if reusable:
        print(f"Reusing {method}: {count:,} pairs, seed {seed}...", flush=True)
    else:
        print(f"Generating {method}: {count:,} pairs, seed {seed}...", flush=True)
        run(binary("generate"), method, seed, count, BUILD)
    if answers.stat().st_size != 8 * (count + 1):
        raise RuntimeError("Unexpected reference answer file size")
    with answers.open("rb") as stream:
        stream.seek(-8, 2)
        expected, = struct.unpack("<d", stream.read(8))
    return pairs, expected


def correctness(regenerate=False):
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
            path, expected = generate(method, 42, count, regenerate=regenerate)
            check(path, count, expected)
            print(f"PASS: {method}, {count:,} pairs (count and reference mean)")


def performance(count, repeats, trace=False, regenerate=False):
    trace_directory = None
    if trace:
        trace_directory = ROOT / "build" / "part2" / "traces" / uuid.uuid4().hex
        trace_directory.mkdir(parents=True)
    path, expected = generate("cluster", 42, count, regenerate=regenerate)
    print("Warm-up and reference check...", flush=True)
    check(path, count, expected)
    samples = []
    for index in range(repeats):
        trace_path = trace_directory / f"run-{index + 1}.json" if trace_directory else None
        elapsed = check(path, count, expected, trace=trace_path)
        samples.append(elapsed)
        print(f"Run {index + 1}: {elapsed:.3f} s, {count / elapsed:,.0f} pairs/s", flush=True)
        if trace_path:
            print(f"Trace: {trace_path}", flush=True)
    median = statistics.median(samples)
    size = path.stat().st_size
    print(f"Input: {count:,} pairs, {size / 1e6:.1f} MB")
    print(f"Median: {median:.3f} s, {count / median:,.0f} pairs/s, {size / median / 1e6:.1f} MB/s")
    print("Release build; includes process startup, file reads, parsing, and math.")
    print("Build/generation excluded; warm-up performed; OS file cache may be warm.")
    if trace:
        print("Tracing and trace flushing are included in these timings. Open traces at https://ui.perfetto.dev/")


def flamegraph(count, regenerate=False):
    if sys.platform != "win32":
        raise RuntimeError("This flamegraph task uses the Windows sampling backend")
    profiler = ROOT / ".tools" / "flamegraph" / "bin" / "flamegraph.exe"
    if not profiler.is_file():
        raise RuntimeError("Install the profiler: cargo install flamegraph --locked --root .tools/flamegraph")
    path, expected = generate("cluster", 42, count, regenerate=regenerate)
    profile_target = ROOT / "build" / "part2" / "profile-cargo"
    environment = os.environ.copy()
    environment.pop("HAVERSINE_TRACE", None)
    environment["CARGO_PROFILE_RELEASE_DEBUG"] = "true"
    print("Building optimized average with debug symbols...", flush=True)
    run("cargo", "build", "--release", "--manifest-path", "part2/Cargo.toml",
        "--bin", "average", "--target-dir", profile_target, env=environment)
    program = profile_target / "release" / "average.exe"
    print("Warm-up and reference check...", flush=True)
    check(path, count, expected)
    output = ROOT / "build" / "part2" / "flamegraphs" / uuid.uuid4().hex / "flamegraph.svg"
    output.parent.mkdir(parents=True)
    print("Approve the Windows administrator prompt to capture CPU samples...", flush=True)
    run("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ROOT / "part2" / "flamegraph.ps1",
        "-Profiler", profiler, "-Program", program, "-InputFile", path,
        "-OutputFile", output, env=environment)
    root = ET.parse(output).getroot()
    if not any(element.tag.endswith("title") and "samples" in (element.text or "")
               for element in root.iter()):
        raise RuntimeError("Flamegraph contains no sampled stacks")
    print(f"CPU flamegraph: {output}")
    print("Open the SVG in a browser. Click frames to zoom; wider frames have more samples.")


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("correctness", "performance", "flamegraph"))
    parser.add_argument("--pairs", type=positive, default=1_000_000)
    parser.add_argument("--repeats", type=positive, default=3)
    parser.add_argument("--trace", action="store_true", help="Export a Perfetto trace for each measured performance run")
    parser.add_argument("--regenerate", action="store_true", help="Replace cached pairs and reference answers")
    args = parser.parse_args()
    try:
        build()
        if args.action == "correctness":
            correctness(regenerate=args.regenerate)
        elif args.action == "flamegraph":
            flamegraph(args.pairs, regenerate=args.regenerate)
        else:
            performance(args.pairs, args.repeats, trace=args.trace, regenerate=args.regenerate)
    except subprocess.CalledProcessError as error:
        print(error.stdout or "", file=sys.stderr)
        print(error.stderr or "", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
