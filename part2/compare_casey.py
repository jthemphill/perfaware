"""Check and benchmark the Rust processor against Casey's vendored listing 67."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import struct
import subprocess
import sys
import time
import uuid

import exercise as ex

VENDOR = ex.ROOT / "vendor" / "computer_enhance"
SOURCE = VENDOR / "perfaware" / "part2"
BUILD = ex.ROOT / "build" / "part2" / "casey"
REL_TOL = 1e-10
ABS_TOL = 1e-8  # km; accounts for differing decimal conversion and summation order.


def invoke(args, cwd=ex.ROOT):
    environment = os.environ.copy()
    environment.pop("HAVERSINE_TRACE", None)
    return subprocess.run([str(arg) for arg in args], cwd=cwd, env=environment,
                          capture_output=True, text=True, timeout=600, check=True)


def build_casey():
    if not (SOURCE / "listing_0067_simple_haversine_main.cpp").is_file():
        raise RuntimeError("Initialize the pinned reference: git submodule update --init vendor/computer_enhance")
    # A Windows Developer terminal supplies the MSVC compiler and SDK together.
    candidates = ("cl", "clang-cl", "clang++", "g++") if sys.platform == "win32" else ("clang++", "g++")
    compiler = os.environ.get("CXX") or next(
        (path for name in candidates if (path := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError("Install a C++ compiler or set CXX to its executable. For MSVC, use a Developer terminal.")
    BUILD.mkdir(parents=True, exist_ok=True)
    msvc = Path(compiler).stem.lower() in ("cl", "clang-cl")
    commands = []
    for name, source in (("average", "listing_0067_simple_haversine_main.cpp"),
                         ("generate", "listing_0066_haversine_generator_main.cpp")):
        output = BUILD / (name + ex.SUFFIX)
        if msvc:
            command = [compiler, "/nologo", "/O2", "/fp:precise", "/EHsc", "/std:c++17",
                       SOURCE / source, f"/Fe:{output}", f"/Fo:{BUILD / (name + '.obj')}"]
        else:
            command = [compiler, "-O3", "-std=c++17", "-ffp-contract=off", SOURCE / source, "-o", output]
        result = invoke(command, cwd=BUILD)
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        commands.append([str(arg) for arg in command])
    version = invoke([compiler, "--version"]).stdout.strip() if not msvc else compiler
    return {"commands": commands, "compiler": version,
            "vendor_revision": invoke(["git", "-C", VENDOR, "rev-parse", "HEAD"]).stdout.strip(),
            "vendor_status": invoke(["git", "-C", VENDOR, "status", "--porcelain"]).stdout.strip()}


def dataset(origin, method, seed, count, regenerate=False):
    if origin == "rust":
        return ex.generate(method, seed, count, regenerate=regenerate)
    # Upstream writes fixed filenames in its working directory. Isolate each run.
    directory = BUILD / "inputs" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    result = invoke([BUILD / ("generate" + ex.SUFFIX), method, seed, count], cwd=directory)
    if "ERROR:" in result.stderr or "Unable to" in result.stderr:
        raise RuntimeError(result.stderr)
    path = directory / f"data_{count}_flex.json"
    answers = directory / f"data_{count}_haveranswer.f64"
    if not path.is_file() or path.stat().st_size == 0 or answers.stat().st_size != 8 * (count + 1):
        raise RuntimeError("Casey's generator did not produce the expected input/reference files")
    with answers.open("rb") as stream:
        stream.seek(-8, 2)
        expected, = struct.unpack("<d", stream.read(8))
    if not math.isfinite(expected):
        raise RuntimeError("Casey's generator returned a nonfinite reference mean")
    return path, expected


def parse_result(name, output, count, expected):
    count_match = re.search(r"^Pair count:\s*(\d+)\s*$", output, re.MULTILINE)
    pattern = (r"^Mean Haversine distance:\s*(\S+)\s+km\s*$" if name == "rust"
               else r"^Haversine sum:\s*(\S+)\s*$")
    mean_match = re.search(pattern, output, re.MULTILINE)
    if not count_match or not mean_match:
        raise RuntimeError(f"{name}: missing count or mean in output:\n{output}")
    actual_count, mean = int(count_match[1]), float(mean_match[1])
    if actual_count != count or not math.isfinite(mean) or not math.isclose(
            mean, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL):
        raise RuntimeError(f"{name}: expected count={count}, mean={expected:.16g}; "
                           f"got count={actual_count}, mean={mean:.16g}")
    return mean


def measure(name, path, count, expected):
    program = ex.binary("average") if name == "rust" else BUILD / ("average" + ex.SUFFIX)
    start = time.perf_counter()
    result = invoke([program, path])
    elapsed = time.perf_counter() - start
    # Casey's CLI can report errors while returning status 0.
    if "ERROR:" in result.stderr:
        raise RuntimeError(f"{name}: {result.stderr}")
    mean = parse_result(name, result.stdout, count, expected)
    return {"seconds": elapsed, "mean_km": mean}


def compare(path, count, expected, order=("rust", "casey")):
    results = {name: measure(name, path, count, expected) for name in order}
    delta = abs(results["rust"]["mean_km"] - results["casey"]["mean_km"])
    if not math.isclose(results["rust"]["mean_km"], results["casey"]["mean_km"],
                        rel_tol=REL_TOL, abs_tol=ABS_TOL):
        raise RuntimeError(f"Rust/Casey mean mismatch: {delta:.12g} km")
    return results, delta


def correctness(regenerate=False):
    cases = [
        ("same_point", '{"x0":12,"y0":34,"x1":12,"y1":34}', 0.0),
        ("quarter_equator", '{"x0":0,"y0":0,"x1":90,"y1":0}', math.pi * ex.RADIUS / 2),
        ("half_equator", '{"x0":0,"y0":0,"x1":180,"y1":0}', math.pi * ex.RADIUS),
        ("exponents_reordered", '{"y1":0E+0,"x1":9e1,"y0":-0.0,"x0":0e-3}', math.pi * ex.RADIUS / 2),
        ("negative_fraction", '{"x0":-45.25,"y0":0,"x1":44.75,"y1":0}', math.pi * ex.RADIUS / 2),
    ]
    for label, pair, expected in cases:
        path = ex.BUILD / f"compare_{label}.json"
        path.write_text('{\n  "pairs": [\n    ' + pair + '\n  ]\n}\n', encoding="utf-8")
        _, delta = compare(path, 1, expected)
        print(f"PASS: {label}, difference {delta:.3g} km")
    for origin in ("rust", "casey"):
        for method in ("uniform", "cluster"):
            for seed in (42, 123):
                for count in (1, 65, 10000):
                    path, expected = dataset(origin, method, seed, count, regenerate)
                    _, delta = compare(path, count, expected)
                    print(f"PASS: {origin} input, {method}, seed {seed}, {count:,} pairs; difference {delta:.3g} km")
    print("PASS: 29 shared-input cases; both counts and means match each other and the reference.")


def benchmark(args, build_info):
    path, expected = dataset(args.dataset, args.method, args.seed, args.pairs, args.regenerate)
    print("Warming up and checking both processors...", flush=True)
    compare(path, args.pairs, expected)
    rounds = []
    for index in range(args.repeats):
        order = ("rust", "casey") if index % 2 == 0 else ("casey", "rust")
        results, delta = compare(path, args.pairs, expected, order)
        rounds.append({"order": list(order), "results": results, "difference_km": delta})
        print(f"Round {index + 1} ({' then '.join(order)}): "
              f"Rust {results['rust']['seconds']:.4f} s; Casey {results['casey']['seconds']:.4f} s; "
              f"difference {delta:.3g} km", flush=True)
    medians = {name: statistics.median(r["results"][name]["seconds"] for r in rounds)
               for name in ("rust", "casey")}
    for name, seconds in medians.items():
        print(f"{name.capitalize()} median: {seconds:.4f} s; {args.pairs / seconds:,.0f} pairs/s; "
              f"{path.stat().st_size / seconds / 1e6:.1f} MB/s")
    ratio = medians["casey"] / medians["rust"]
    print(f"Casey/Rust elapsed-time ratio: {ratio:.3f} (>1 means Rust is faster)")
    print("End-to-end: startup, reads, parsing, math, output, and process cleanup; builds/generation excluded.")
    print("Both warmed up; OS cache may be warm. Tracing disabled. Casey materializes JSON; Rust streams it.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    report = {
        "input": {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size,
                  "pairs": args.pairs, "generator": args.dataset, "method": args.method,
                  "seed": args.seed, "expected_mean_km": expected},
        "tolerance": {"relative": REL_TOL, "absolute_km": ABS_TOL},
        "casey_build": build_info, "rustc": invoke(["rustc", "--version"]).stdout.strip(),
        "host": platform.platform(), "machine": platform.machine(),
        "rounds": rounds, "median_seconds": medians, "casey_over_rust": ratio,
    }
    output = BUILD / "benchmarks" / f"{uuid.uuid4().hex}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Benchmark report: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "benchmark"))
    parser.add_argument("--pairs", type=ex.positive, default=1_000_000)
    parser.add_argument("--repeats", type=ex.positive, default=6)
    parser.add_argument("--dataset", choices=("rust", "casey"), default="rust")
    parser.add_argument("--method", choices=("uniform", "cluster"), default="cluster")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--regenerate", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.seed < 2**63:
        parser.error("--seed must be between 0 and 2^63-1 (supported by both generators)")
    try:
        ex.build()
        print("Building Casey's vendored processor and generator...", flush=True)
        build_info = build_casey()
        if args.action == "check":
            correctness(args.regenerate)
        else:
            benchmark(args, build_info)
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
