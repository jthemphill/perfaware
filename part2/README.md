# Part 2: Haversine input generator

A Rust package with no external dependencies. The `generate` binary lives in
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

`average` provides command-line handling, byte-oriented file loading, a `Pair`
type, and result printing. Implement `parse_pairs` and `average_haversine` yourself.
Both currently return explicit "not implemented" errors. No JSON library is used.
The generator's `haversine` function is available as a reference for the math.

```powershell
cargo run --release --manifest-path part2/Cargo.toml --bin generate -- cluster 42 10
cargo run --manifest-path part2/Cargo.toml --bin average -- build/part2/data_cluster_42_10.json
```

Start with the small generated file. As you implement the parser, check whitespace,
negative and fractional numbers, exponents, reordered fields, empty arrays, and
malformed or truncated input. Compare the parsed pair count and computed mean
against the generator's output. The scaffold reads the entire file into memory.

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
