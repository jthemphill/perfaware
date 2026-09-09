# Part 1: 8086 disassembler

Start in `part1/8086_disassembler.py`, inside `decode_instruction(data, offset)`.
Run the commands below from the repository root. The decoder, instruction loop,
and command-line interface are in this part's directory.

This stage turns machine-code bytes into assembly text. The wider course later
builds a CPU simulation that executes instructions and tracks machine state.
Lesson: https://www.computerenhance.com/p/instruction-decoding-on-the-8086

The supported regression listings are 0037–0041, covering MOV, arithmetic,
conditional jumps, and loops. Each decoded instruction returns its assembly text
and the number of bytes consumed.

## VS Code

Open the repository root in VS Code and install the recommended Python and
debugger extensions. Tasks and debug configurations select Windows or macOS
Python automatically after you create `.venv` on that computer.

| Shortcut / task | Action |
| --- | --- |
| **F5** | Debug the selected listing; inputs assemble automatically. Stops at your breakpoints. |
| **Ctrl+F5** | Run the selected listing without debugging. |
| **Shift+F5** | Stop debugging. |
| **F9** | Toggle a breakpoint, for example inside `decode_instruction`. |
| **F10 / F11** | Step over / step into. Inspect `data` and `offset` in Variables. |
| **Ctrl+Shift+B** | Assemble and check supported listings (0037–0041). |
| **Tasks: Run Task â†’ 8086: Check all upstream listings** | Try every upstream part1 assembly listing; later exercises will fail until implemented. |
| **Tasks: Run Task â†’ 8086: Sync course listings** | Fetch and check out the latest upstream revision. |
| **Tasks: Run Task â†’ 8086: Run listing** | Choose a listing and print your disassembly. |
| **Tasks: Run Task â†’ 8086: Inspect bytes** | Show each input byte in hex and binary. |
| **Tasks: Run Task â†’ 8086: Assemble inputs** | Generate raw binaries only. |

Choose listing 0037 or 0038 once in the Run and Debug dropdown; F5 and Ctrl+F5
reuse that choice without prompting. Files are saved before tasks and debugging.
Direct `8086: Run 0037/0038` and `8086: Check 0037/0038` tasks are also available.
Task output reuses a cleared panel to keep each run readable.

Python does not need a compilation step; NASM compiles the exercise assembly
into the raw bytes that your program reads.

## Command line (PowerShell)

```powershell
.\.venv\Scripts\python.exe part1/exercise.py assemble
.\.venv\Scripts\python.exe part1/exercise.py bytes 0037
.\.venv\Scripts\python.exe part1/exercise.py run 0037
.\.venv\Scripts\python.exe part1/exercise.py check
.\.venv\Scripts\python.exe part1/exercise.py check 0039
.\.venv\Scripts\python.exe part1/exercise.py check all
.\.venv\Scripts\python.exe part1/8086_disassembler.py build/part1/listing_0037_single_register_mov.bin
```

On macOS, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` in
these commands, for example `.venv/bin/python part1/exercise.py check`.

The checker assembles the original listing, disassembles that binary, then
reassembles your output and compares the two binaries byte-for-byte.
Assembly text is not compared.
This is tailored to the supported exercises; instructions with multiple
equivalent encodings may require relaxing the byte comparison.

## Repository layout and course updates

```text
part1/8086_disassembler.py      Your decoder
part1/exercise.py       Assemble, run, and compare listings
.vscode/                  Editor tasks and debugger configurations
vendor/computer_enhance/  Official course repository (Git submodule)
build/part1/                    Generated binaries and disassembly (ignored)
.tools/                   Local NASM installation (ignored)
.venv/                    Local Python environment (ignored)
```

Listings are read directly from `vendor/computer_enhance/perfaware/part1/`.
Do not edit these upstream files for your implementation. The submodule pins a
specific upstream commit, so updates are explicit and reproducible.

After cloning this project, initialize its course dependency:

```powershell
git submodule update --init --recursive
```

To sync with the latest upstream revision:

```powershell
git submodule update --init --remote vendor/computer_enhance
git add vendor/computer_enhance
```

Commit the updated submodule pointer with your project changes to record the
revision. Syncing is manual, not a background operation.

The runner defaults to `supported`: listings 0037–0041. Extend
`SUPPORTED_LISTINGS` in `part1/exercise.py` as your decoder grows. Pass a listing
number to try another exercise, or `all` to discover every upstream part1 `.asm`
file. The latter includes later non-8086 exercises and is not expected to pass
with this decoder. Update the VS Code listing pickers and debug configurations
when adding exercises to your regular workflow.

## Local tools and recreating the environment

Use Python 3.9 or newer. Create `.venv` on each computer with
`py -3 -m venv .venv` on Windows (or `python -m venv .venv` if the launcher is
unavailable), or `python3 -m venv .venv` on macOS. No Python packages are needed.
Do not copy a virtual environment from one operating system to the other.

On Windows, extract portable NASM 3.02 into `.tools/` from the official release:
https://www.nasm.us/pub/nasm/releasebuilds/3.02/win64/nasm-3.02-win64.zip
The executable should be `.tools/nasm-3.02/nasm.exe`. Alternatively, install
NASM on PATH.

On macOS, install NASM on PATH (for example, `brew install nasm` if you use
Homebrew), or place a macOS NASM executable at `.tools/nasm-3.02/nasm`.
The runner prefers the local executable for the current operating system,
then searches PATH. A leftover Windows `nasm.exe` is ignored on macOS.
Virtual environments, tools, and generated outputs are ignored by Git.
