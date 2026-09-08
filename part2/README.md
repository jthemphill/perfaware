# Part 2: Haversine generator and streaming average

## VS Code checks

Use **Ctrl+Shift+P → Tasks: Run Task**:

- **Haversine: Benchmark with Perfetto traces** runs the scale benchmark with
  tracing enabled for each of its three measured runs. A unique directory under
  `build/part2/traces/` holds `run-1.json` through `run-3.json`; paths are printed
  in the terminal. Open a file in https://ui.perfetto.dev/. These timings include
  tracing and flushing overhead. The warm-up is not traced. CLI equivalent:
  `.\.venv\Scripts\python.exe part2/exercise.py performance --pairs 1000000 --trace`.

- **Haversine: Check correctness** builds the release binaries and checks known
  distances plus uniform and clustered datasets at 1, 65, and 10,000 pairs.
  It checks the count and mean against the generator's binary reference answer.
- **Haversine: Benchmark at scale** prompts for a pair count (default 1,000,000),
  generates clustered input, warms up once, then measures three runs. Every run
  also verifies the count and mean. Reports elapsed time, pairs/s, and MB/s.

Timing includes process startup, file reads, parsing, and Haversine calculation;
it excludes compilation and generation. The OS file cache may be warm. This is
an end-to-end benchmark, not an isolated math-function benchmark.

Both commands fail with a nonzero exit code on errors or mismatches. Mean
comparisons allow absolute error of 1e-8 km or relative error of 1e-10 to account
for floating-point accumulation differences. Generated inputs and references
live in `build/part2/checks/`; release binaries live in `build/part2/cargo/`.

Equivalent commands from the repository root:

```powershell
.\.venv\Scripts\python.exe part2/exercise.py correctness
.\.venv\Scripts\python.exe part2/exercise.py performance --pairs 1000000 --repeats 3
```

A Rust package using `tracing` and `tracing-chrome` for optional profiling. The `generate` binary lives in
`src/bin/generate.rs`; the averaging exercise lives in `src/bin/average.rs`.
Run from the repository root:

```powershell
cargo run --release --manifest-path part2/Cargo.toml --bin generate -- cluster 42 1000000
cargo run --release --manifest-path part2/Cargo.toml --bin generate -- uniform 42 10
cargo test --manifest-path part2/Cargo.toml
```

Arguments: `uniform|cluster`, unsigned 64-bit seed, positive pair count, and an
optional output directory. The default is this repository's `build/part2/`.
Repeated runs with the same method, seed, and count overwrite the same files.
Zero pairs are rejected because their average is undefined.

The generator streams both files through buffered writers, using constant memory:

- `data_<method>_<seed>_<count>.json`: `{"pairs":[{"x0":...,"y0":...,"x1":...,"y1":...},...]}`.
  X is longitude in degrees, Y is latitude. Decimal coordinates round-trip to f64.
- `data_<method>_<seed>_<count>.f64`: one little-endian f64 distance per pair,
  followed by one f64 containing the **mean**, for exactly `8 * (count + 1)` bytes.
  Distances use radius 6372.8 km and the course's Haversine formula, with its
  intermediate value clamped to [0, 1] to guard against floating-point roundoff.
  The mean uses compensated summation. Answers are computed before JSON encoding.

## Averaging exercise

### Perfetto traces

Set `HAVERSINE_TRACE` to a new output filename to enable Chrome Trace Event JSON
export, then open it in [Perfetto](https://ui.perfetto.dev/). The parent directory
must exist; an existing file is rejected to avoid overwriting input or old traces.

```powershell
$env:HAVERSINE_TRACE = "build/part2/average-trace.json"
try {
    cargo run --release --manifest-path part2/Cargo.toml --bin average -- build/part2/data_cluster_42_10.json
} finally {
    Remove-Item Env:HAVERSINE_TRACE
}
```

Spans cover `haversine_run`, `open_input`, `average_haversine`, and
`parse_and_average_batch` (up to 10,000 pairs, with starting pair and byte offset).
Batch spans include both parsing/file reads and distance calculation. They do
not separate individual function timings. The trace is flushed on success and
normal error returns. Tracing is disabled when the environment variable is unset;
leave it unset for ordinary performance comparisons.

`average` streams pairs through a cursor over `BufRead`, calculates their
distances, and prints the count and mean. No JSON library is used.
The generator's `haversine` function is available as a reference for the math.

```powershell
cargo run --release --manifest-path part2/Cargo.toml --bin generate -- cluster 42 10
cargo run --manifest-path part2/Cargo.toml --bin average -- build/part2/data_cluster_42_10.json
```

Start with the small generated file. As you implement the parser, check whitespace,
negative and fractional numbers, exponents, reordered fields, empty arrays, and
malformed or truncated input. Compare the parsed pair count and computed mean
against the generator's output. The parser keeps one pair and a bounded number
token in memory rather than loading the entire file.

## Clustering

Cluster mode divides pairs into `min(64, count)` contiguous groups. Sizes differ
by at most one; the first groups receive any remainder. Each group picks a random
longitude/latitude center and independent angular half-widths (0.1 to 180 degrees
for longitude, 0.1 to 90 for latitude). Bounds are clipped to valid coordinates.
Both endpoints are sampled independently inside the same rectangle.

These are rectangles in longitude/latitude, not circular spherical caps; the
sampling is uniform in coordinates, not in surface area. Uniform mode uses the
whole coordinate range for every pair. SplitMix64 supplies seeded randomness.

Different cluster extents produce different expected distances, making omission
of contiguous chunks easier to notice in the mean. The fixed group count keeps
that variation as the dataset grows. This is a diagnostic, not a guarantee:
skipping the same fraction of every group can still look correct. A future
processor should check the pair count and individual reference answers as well.

Lesson: [Generating Haversine Input JSON](https://www.computerenhance.com/p/generating-haversine-input-json).
