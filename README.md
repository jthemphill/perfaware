# 8086 disassembler exercises

Start in `8086_disassembler.py`, inside `decode_instruction(data, offset)`.
File reading, the instruction loop, assembly output, and the command-line interface
are ready. The actual decoding is intentionally yours to implement.

This stage turns machine-code bytes into assembly text. The wider course later
builds a CPU simulation that executes instructions and tracks machine state.
Lesson: https://www.computerenhance.com/p/instruction-decoding-on-the-8086

## Your first goal

1. Implement register-to-register MOV for listing 0037.
2. Return an instruction string and the number of bytes consumed.
3. Extend/verify it against listing 0038, including byte and word registers.
4. Reject unsupported or truncated encodings with `ValueError`.

Use the instruction-encoding tables in the lesson/manual to work out the fields.
The scaffold does not contain the decoder solution.

## VS Code

Open this folder in VS Code. Python and debugger extensions are already installed.

| Shortcut / task | Action |
| --- | --- |
| **F5** | Debug the selected listing; inputs assemble automatically. Stops at your breakpoints. |
| **Ctrl+F5** | Run the selected listing without debugging. |
| **Shift+F5** | Stop debugging. |
| **F9** | Toggle a breakpoint, for example inside `decode_instruction`. |
| **F10 / F11** | Step over / step into. Inspect `data` and `offset` in Variables. |
| **Ctrl+Shift+B** | Assemble and check supported listings (0037 and 0038). |
| **Tasks: Run Task → 8086: Check all upstream listings** | Try every upstream part1 assembly listing; later exercises will fail until implemented. |
| **Tasks: Run Task → 8086: Sync course listings** | Fetch and check out the latest upstream revision. |
| **Tasks: Run Task → 8086: Run listing** | Choose a listing and print your disassembly. |
| **Tasks: Run Task → 8086: Inspect bytes** | Show each input byte in hex and binary. |
| **Tasks: Run Task → 8086: Assemble inputs** | Generate raw binaries only. |

Choose listing 0037 or 0038 once in the Run and Debug dropdown; F5 and Ctrl+F5
reuse that choice without prompting. Files are saved before tasks and debugging.
Direct `8086: Run 0037/0038` and `8086: Check 0037/0038` tasks are also available.
Task output reuses a cleared panel to keep each run readable.

Python does not need a compilation step; NASM compiles the exercise assembly
into the raw bytes that your program reads.

## Command line (PowerShell)

```powershell
.\.venv\Scripts\python.exe scripts/exercise.py assemble
.\.venv\Scripts\python.exe scripts/exercise.py bytes 0037
.\.venv\Scripts\python.exe scripts/exercise.py run 0037
.\.venv\Scripts\python.exe scripts/exercise.py check
.\.venv\Scripts\python.exe scripts/exercise.py check 0039
.\.venv\Scripts\python.exe scripts/exercise.py check all
.\.venv\Scripts\python.exe 8086_disassembler.py build/listing_0037_single_register_mov.bin
```

The checker assembles the original listing, disassembles that binary, then
reassembles your output and compares the two binaries byte-for-byte.
Assembly text is not compared.
This is tailored to the current MOV exercises; later instructions with multiple
equivalent encodings may require relaxing the byte comparison.

## Repository layout and course updates

```text
8086_disassembler.py      Your decoder
scripts/exercise.py       Assemble, run, and compare listings
.vscode/                  Editor tasks and debugger configurations
vendor/computer_enhance/  Official course repository (Git submodule)
build/                    Generated binaries and disassembly (ignored)
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

The runner defaults to `supported`: listings 0037 and 0038. Extend
`SUPPORTED_LISTINGS` in `scripts/exercise.py` as your decoder grows. Pass a listing
number to try another exercise, or `all` to discover every upstream part1 `.asm`
file. The latter includes later non-8086 exercises and is not expected to pass
with this decoder. Update the VS Code listing pickers and debug configurations
when adding exercises to your regular workflow.

## Local tools and recreating the environment

A project virtual environment is ready in `.venv/`, created using the available
bundled Python runtime because the Windows Python launcher was not usable here.
It depends on that base runtime remaining installed. No Python packages are needed.
To recreate it with a working Python installation, run `python -m venv .venv`.

Portable NASM 3.02 is in `.tools/nasm-3.02/`, downloaded from the official release:
https://www.nasm.us/pub/nasm/releasebuilds/3.02/win64/nasm-3.02-win64.zip
To recreate it, extract that archive into `.tools/`, or install NASM on PATH.
The runner prefers the local copy. No global PATH changes are needed.
Virtual environments, tools, and generated outputs are ignored by Git.
