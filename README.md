# Performance-Aware Programming coursework

Solutions and tools organized by course part.

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
