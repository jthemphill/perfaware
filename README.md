# Performance-Aware Programming coursework

Solutions and tools organized by course part.

## Windows and macOS setup

Create a separate Python environment on each computer; `.venv/` and `.tools/`
contain platform-specific executables and should not be copied between them.
Python 3.9 or newer is supported. From the repository root:

| Setup | Windows (PowerShell) | macOS (Terminal) |
| --- | --- | --- |
| Python environment | `py -3 -m venv .venv` | `python3 -m venv .venv` |
| Part 1 check | `.venv/Scripts/python.exe part1/exercise.py check` | `.venv/bin/python part1/exercise.py check` |
| Part 2 check | `.venv/Scripts/python.exe part2/exercise.py correctness` | `.venv/bin/python part2/exercise.py correctness` |

No Python packages are required. Initialize the course source with
`git submodule update --init --recursive`. Part 1 needs NASM (see
[tool setup](part1/README.md#local-tools-and-recreating-the-environment));
part 2 needs [rustup](https://rustup.rs/). Run `rustup show active-toolchain`
from this checkout to install the version and components pinned in
`rust-toolchain.toml` (currently Rust 1.94.0). The pin selects the native host
toolchain on each computer without changing your global default. Comparing against
Casey additionally needs a C++ compiler, and CPU sampling needs the profiler
described in [part 2](part2/README.md).

The same VS Code tasks and debug configurations work on both systems and choose
the appropriate `.venv` executable automatically. Install the recommended Python
Environments extension to discover `./.venv`. Run **Python: Select Interpreter**
once per computer and choose the actual executable inside that environment
(`.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on macOS).
The selection is machine-local; do not commit an absolute interpreter path.

If isort or Black reports `spawn .../.venv ENOENT`, select the executable again,
then run **Developer: Reload Window**. Some extension versions pass a directory
configured as `python.defaultInterpreterPath` directly to subprocess launch;
the shared settings deliberately use environment discovery instead.
Reload the window after installing the Rust toolchain as well if rust-analyzer
still reports the old nightly version. No nightly features are required.

## Portability boundaries

- **Algorithms and formats:** the Python decoder and Rust Haversine code stay
  independent of OS APIs. Data files use explicit little-endian encoding.
- **Timing:** `part2/src/timer/` exposes ticks, frequency, and a clock name.
  x86-64 reads TSC directly; AArch64 (including Apple Silicon) reads
  `CNTVCT_EL0` directly and gets its frequency from `CNTFRQ_EL0`. Selection is
  by CPU architecture, with no OS calls or runtime dispatch in either read.
  Other architectures fall back to Rust's `Instant`; `portable-timer` explicitly
  opts into that slower fallback on any host. Compare elapsed seconds or
  throughput, not raw tick counts.
- **Tooling:** Python runners own executable suffixes, compiler discovery, and
  sampler selection. CPU sampling retains native backends: flamegraph on Windows
  and samply on macOS. Recreate `.venv`, `.tools`, and build outputs locally.
- **Reference code:** the vendored course source stays unchanged. The supported
  Casey comparison compiles listings 66/67 natively; later Windows/x86-specific
  course experiments are not promised to run on every platform.

`.github/workflows/check.yml` runs Rust tests with both native and portable
clocks, Python runner tests, NASM round trips, Haversine correctness, and the
Casey comparison on Windows x64, macOS Intel, and macOS Apple Silicon. It runs
on push and pull requests; sampling remains a local check because it depends
on OS permissions. Keep the toolchain pin and CI checks together when upgrading.

## C++ reference browsing

For Casey's C++ listings, install the recommended Microsoft C/C++ extension
and run **Tasks: Run Task → Casey: Configure C++ IntelliSense** once on each
computer, and again after moving the checkout or updating the course source.
This requires a C++ compiler (`CXX` can select its executable; for MSVC, run
from a Developer terminal). The task generates an ignored, machine-local
`build/casey-intellisense/compile_commands.json` containing the main listings.
IntelliSense then parses included `.cpp` fragments in their main listing's
context, where Casey defines types such as `u64`, `f64`, and `buffer`.
On macOS the editor database targets x86-64 so the course's RDTSC/AVX intrinsics
parse on Apple Silicon; this does not change benchmark builds. Windows-only
listings still require Windows headers and may report errors on macOS/Linux.

## Part 1: 8086 disassembler

The decoder and its test runner live in [part1/](part1/).
See [part1/README.md](part1/README.md) for debugging, testing, and tool setup.

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe part1/exercise.py check
```

In VS Code, **Ctrl+Shift+B** checks the supported part 1 listings.

## Part 2: Haversine input generator

The Rust generator in [part2/](part2/) produces uniform or clustered point pairs
and binary reference distances. See [part2/README.md](part2/README.md).

```powershell
cargo run --release --manifest-path part2/Cargo.toml --bin generate -- cluster 42 1000000
```

## Layout

```text
part1/                   8086 decoder, exercise runner, and documentation
part2/                   Rust Haversine input generator
build/part2/             Generated JSON and reference distances (ignored)
build/part1/             Generated part 1 binaries and disassembly (ignored)
vendor/computer_enhance/ Official course source (Git submodule)
.vscode/                 Workspace tasks and debugger configurations
.tools/                  Shared local tools (ignored)
.venv/                   Shared Python environment (ignored)
```

Future coursework can live alongside `part1/` in its own part directory.
Open the repository root as the VS Code workspace.

## Course source

Initialize the pinned course revision after cloning:

```powershell
git submodule update --init --recursive
```

To update to the latest upstream revision:

```powershell
git submodule update --init --remote vendor/computer_enhance
```

Commit the updated submodule pointer to record the new revision. Listings are
read directly from the submodule; there are no separate local copies to sync.
