"""CLI interface for mutation-lite."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from mutation_lite import MutationError, SubprocessRunner, generate_mutants, run_mutants


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="mutation-lite", description="AST mutation testing tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command: 'list FILE'
    list_parser = subparsers.add_parser("list", help="List mutants for FILE")
    list_parser.add_argument("file", help="Python file to mutate")

    # run command: 'run FILE --root DIR -- CMD...'
    run_parser = subparsers.add_parser("run", help="Run mutants for FILE")
    run_parser.add_argument("file", help="Python file to mutate")
    run_parser.add_argument("--root", required=True, help="Root directory to copy")

    argv = list(argv)
    # Split at '--' first: argparse.REMAINDER after the positional FILE would swallow '--root DIR'.
    tail: list[str] = []
    if "--" in argv:
        cut = argv.index("--")
        argv, tail = argv[:cut], argv[cut + 1 :]
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

    file_path = Path(args.file)
    if not file_path.is_file():
        sys.stderr.write(f"File not found: {args.file}\n")
        return 2

    source = file_path.read_text(encoding="utf-8")

    try:
        mutants = generate_mutants(args.file, source)
    except MutationError as e:
        sys.stderr.write(f"Mutation error ({e.code}): {e}\n")
        return 2

    if args.command == "list":
        for m in mutants:
            print(f"{m.id} {m.original} -> {m.replacement}")
        return 0

    if args.command == "run":
        cmd = tail
        if not cmd:
            sys.stderr.write("Error: No test command specified after --\n")
            return 2

        runner = SubprocessRunner(command=cmd, root=Path(args.root))
        report = run_mutants(mutants, runner)
        if report.survivors:
            print(f"Survivors: {len(report.survivors)}")
            for surv in report.survivors:
                print(f"  {surv}")
            return 1
        print("All mutants killed or timed out.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
