"""Save flamegraph's folded stacks for Perfetto and pass them through to the SVG renderer."""

from pathlib import Path
import sys


def validate_stacks(data):
    total = 0
    for line in data.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stack, separator, count = line.rpartition(" ")
        if not separator or not stack.strip() or not count.isascii() or not count.isdecimal() or int(count) <= 0:
            raise ValueError("Invalid collapsed stack: expected a stack followed by a positive sample count")
        total += int(count)
    if total == 0:
        raise ValueError("Profile contains no sampled stacks; try a larger pair count")
    return total


def main():
    data = sys.stdin.buffer.read()
    validate_stacks(data)
    # flamegraph runs this hook in the unique capture directory.
    with Path("flamegraph.collapsed").open("xb") as output:
        output.write(data)
    sys.stdout.buffer.write(data)


if __name__ == "__main__":
    main()
