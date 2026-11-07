"""Lightweight ast-based mutation testing for Python."""

from __future__ import annotations

import ast
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

__all__ = [
    "OPERATORS",
    "Mutant",
    "MutantEvent",
    "MutantResult",
    "MutationError",
    "Report",
    "SubprocessRunner",
    "TestRunner",
    "__version__",
    "generate_mutants",
    "run_mutants",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

OPERATORS: tuple[str, ...] = ("AOR", "ROR", "LCR", "UOI", "CRP", "RET", "SDL")
ErrorCode = Literal["syntax_error", "too_many_mutants", "invalid_option"]
Outcome = Literal["killed", "survived", "timeout", "error"]


class MutationError(Exception):
    """Base exception for mutation-lite errors with a stable machine-readable code."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: ErrorCode = code


@dataclass(frozen=True)
class Mutant:
    """A single code mutation at a specific span in a source file."""

    id: str
    path: str
    line: int
    col: int
    operator: str
    original: str
    replacement: str
    _source: str
    _start_char: int
    _end_char: int

    def mutated_source(self) -> str:
        """Return the full source text with this mutation applied."""
        return self._source[: self._start_char] + self.replacement + self._source[self._end_char :]


@dataclass(frozen=True)
class MutantEvent:
    """Event dispatched when a mutant run completes."""

    id: str
    outcome: Outcome


@dataclass(frozen=True)
class MutantResult:
    """Result of executing tests against a mutant."""

    id: str
    outcome: Outcome
    detail: str | None = None


@dataclass(frozen=True)
class Report:
    """Summary report of a mutation test run."""

    results: tuple[MutantResult, ...]
    score: float | None
    survivors: tuple[str, ...]


class TestRunner(Protocol):
    """Protocol for mutation test runners."""

    def run(self, mutant: Mutant) -> Literal["killed", "survived", "timeout"]:
        """Execute test suite against the mutant."""
        ...


class SubprocessRunner:
    """Runner that copies a root directory to a temporary path and runs a command."""

    def __init__(self, command: Sequence[str], root: Path, *, timeout_s: float = 60.0) -> None:
        self.command = list(command)
        self.root = Path(root).resolve()
        self.timeout_s = timeout_s

    def run(self, mutant: Mutant) -> Literal["killed", "survived", "timeout"]:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Copy root contents into temp_dir
            shutil.copytree(self.root, temp_path, dirs_exist_ok=True)
            # Determine path to mutated file in temp directory
            mutant_p = Path(mutant.path)
            try:
                rel_path = mutant_p.relative_to(self.root)
            except ValueError:
                # If mutant.path is relative, keep it; if absolute outside root, use filename
                rel_path = mutant_p if not mutant_p.is_absolute() else Path(mutant_p.name)
            target_file = (temp_path / rel_path).resolve()
            # If mutant.path was relative, resolve relative to temp_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(mutant.mutated_source(), encoding="utf-8")

            try:
                proc = subprocess.run(
                    self.command,
                    cwd=temp_path,
                    capture_output=True,
                    timeout=self.timeout_s,
                    check=False,
                )
                if proc.returncode == 0:
                    return "survived"
                return "killed"
            except subprocess.TimeoutExpired:
                return "timeout"


def _byte_to_char_offset(line_bytes: bytes, byte_offset: int) -> int:
    """Convert a UTF-8 byte offset in line_bytes to a character index."""
    valid_slice = line_bytes[:byte_offset]
    return len(valid_slice.decode("utf-8", errors="replace"))


class _MutantCollector(ast.NodeVisitor):
    def __init__(
        self,
        path: str,
        source: str,
        active_ops: set[str],
        line_offsets: list[int],
        lines_bytes: list[bytes],
    ) -> None:
        self.path = path
        self.source = source
        self.active_ops = active_ops
        self.line_offsets = line_offsets
        self.lines_bytes = lines_bytes
        self.candidates: list[dict[str, Any]] = []

        # Track AST nodes to ignore
        self.ignored_nodes: set[int] = set()
        self.ignored_lines: set[int] = set()

        # Identify lines with pragma
        for lineno, line_b in enumerate(lines_bytes, start=1):
            line_str = line_b.decode("utf-8", errors="replace")
            if "# pragma: no mutate" in line_str:
                self.ignored_lines.add(lineno)

    def _get_char_span(self, node: ast.AST) -> tuple[int, int]:
        start_line = getattr(node, "lineno", 1) - 1
        start_col = getattr(node, "col_offset", 0)
        end_line = getattr(node, "end_lineno", 1) - 1
        end_col = getattr(node, "end_col_offset", 0)

        start_char_in_line = _byte_to_char_offset(self.lines_bytes[start_line], start_col)
        end_char_in_line = _byte_to_char_offset(self.lines_bytes[end_line], end_col)

        start_char = self.line_offsets[start_line] + start_char_in_line
        end_char = self.line_offsets[end_line] + end_char_in_line
        return start_char, end_char

    def _is_ignored(self, node: ast.AST) -> bool:
        if id(node) in self.ignored_nodes:
            return True
        lineno = getattr(node, "lineno", None)
        return bool(lineno is not None and lineno in self.ignored_lines)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for dec in node.decorator_list:
            self.ignored_nodes.add(id(dec))
        if node.returns:
            self.ignored_nodes.add(id(node.returns))
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self.ignored_nodes.add(id(arg.annotation))
        if node.args.vararg and node.args.vararg.annotation:
            self.ignored_nodes.add(id(node.args.vararg.annotation))
        if node.args.kwarg and node.args.kwarg.annotation:
            self.ignored_nodes.add(id(node.args.kwarg.annotation))
        # Ignore docstring
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            self.ignored_nodes.add(id(node.body[0]))
            self.ignored_nodes.add(id(node.body[0].value))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        for dec in node.decorator_list:
            self.ignored_nodes.add(id(dec))
        if node.returns:
            self.ignored_nodes.add(id(node.returns))
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self.ignored_nodes.add(id(arg.annotation))
        if node.args.vararg and node.args.vararg.annotation:
            self.ignored_nodes.add(id(node.args.vararg.annotation))
        if node.args.kwarg and node.args.kwarg.annotation:
            self.ignored_nodes.add(id(node.args.kwarg.annotation))
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            self.ignored_nodes.add(id(node.body[0]))
            self.ignored_nodes.add(id(node.body[0].value))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for dec in node.decorator_list:
            self.ignored_nodes.add(id(dec))
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            self.ignored_nodes.add(id(node.body[0]))
            self.ignored_nodes.add(id(node.body[0].value))
        self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> None:
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            self.ignored_nodes.add(id(node.body[0]))
            self.ignored_nodes.add(id(node.body[0].value))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.ignored_nodes.add(id(node.annotation))
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # Skip f-string internals
        self.ignored_nodes.add(id(node))
        for child in ast.walk(node):
            self.ignored_nodes.add(id(child))

    def visit_Expr(self, node: ast.Expr) -> None:
        if self._is_ignored(node):
            return
        # SDL: Statement Deletion Operator for expression statement that is a call
        if "SDL" in self.active_ops and isinstance(node.value, ast.Call):
            start_char, end_char = self._get_char_span(node)
            original = self.source[start_char:end_char]
            self.candidates.append(
                {
                    "node": node,
                    "operator": "SDL",
                    "original": original,
                    "replacement": "pass",
                    "start_char": start_char,
                    "end_char": end_char,
                    "line": node.lineno,
                    "col": node.col_offset,
                }
            )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if self._is_ignored(node):
            return
        # RET: replaces 'return <expr>' (expr not None and not Constant(None)) with 'return None'
        if (
            "RET" in self.active_ops
            and node.value is not None
            and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        ):
            start_char, end_char = self._get_char_span(node)
            original = self.source[start_char:end_char]
            self.candidates.append(
                {
                    "node": node,
                    "operator": "RET",
                    "original": original,
                    "replacement": "return None",
                    "start_char": start_char,
                    "end_char": end_char,
                    "line": node.lineno,
                    "col": node.col_offset,
                }
            )
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if self._is_ignored(node):
            return
        if "AOR" in self.active_ops:
            aor_map: dict[type[ast.operator], type[ast.operator]] = {
                ast.Add: ast.Sub,
                ast.Sub: ast.Add,
                ast.Mult: ast.Div,
                ast.Div: ast.Mult,
                ast.FloorDiv: ast.Mod,
                ast.Mod: ast.FloorDiv,
            }
            op_type = type(node.op)
            if op_type in aor_map:
                mut_op = aor_map[op_type]()
                new_node = ast.BinOp(left=node.left, op=mut_op, right=node.right)
                ast.copy_location(new_node, node)
                replacement = ast.unparse(new_node)
                start_char, end_char = self._get_char_span(node)
                original = self.source[start_char:end_char]
                self.candidates.append(
                    {
                        "node": node,
                        "operator": "AOR",
                        "original": original,
                        "replacement": replacement,
                        "start_char": start_char,
                        "end_char": end_char,
                        "line": node.lineno,
                        "col": node.col_offset,
                    }
                )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if self._is_ignored(node):
            return
        if "ROR" in self.active_ops:
            ror_map: dict[type[ast.cmpop], type[ast.cmpop]] = {
                ast.Lt: ast.LtE,
                ast.LtE: ast.Lt,
                ast.Gt: ast.GtE,
                ast.GtE: ast.Gt,
                ast.Eq: ast.NotEq,
                ast.NotEq: ast.Eq,
                ast.Is: ast.IsNot,
                ast.IsNot: ast.Is,
                ast.In: ast.NotIn,
                ast.NotIn: ast.In,
            }
            for idx, op in enumerate(node.ops):
                op_type = type(op)
                if op_type in ror_map:
                    mut_ops = list(node.ops)
                    mut_ops[idx] = ror_map[op_type]()
                    new_node = ast.Compare(
                        left=node.left, ops=mut_ops, comparators=node.comparators
                    )
                    ast.copy_location(new_node, node)
                    replacement = ast.unparse(new_node)
                    start_char, end_char = self._get_char_span(node)
                    original = self.source[start_char:end_char]
                    self.candidates.append(
                        {
                            "node": node,
                            "operator": "ROR",
                            "original": original,
                            "replacement": replacement,
                            "start_char": start_char,
                            "end_char": end_char,
                            "line": node.lineno,
                            "col": node.col_offset,
                        }
                    )
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if self._is_ignored(node):
            return
        if "LCR" in self.active_ops:
            mut_op: ast.boolop | None
            if isinstance(node.op, ast.And):
                mut_op = ast.Or()
            elif isinstance(node.op, ast.Or):
                mut_op = ast.And()
            else:
                mut_op = None

            if mut_op is not None:
                new_node = ast.BoolOp(op=mut_op, values=node.values)
                ast.copy_location(new_node, node)
                replacement = ast.unparse(new_node)
                start_char, end_char = self._get_char_span(node)
                original = self.source[start_char:end_char]
                self.candidates.append(
                    {
                        "node": node,
                        "operator": "LCR",
                        "original": original,
                        "replacement": replacement,
                        "start_char": start_char,
                        "end_char": end_char,
                        "line": node.lineno,
                        "col": node.col_offset,
                    }
                )
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if self._is_ignored(node):
            return
        if "UOI" in self.active_ops and isinstance(node.op, ast.Not):
            new_node = node.operand
            replacement = ast.unparse(new_node)
            start_char, end_char = self._get_char_span(node)
            original = self.source[start_char:end_char]
            self.candidates.append(
                {
                    "node": node,
                    "operator": "UOI",
                    "original": original,
                    "replacement": replacement,
                    "start_char": start_char,
                    "end_char": end_char,
                    "line": node.lineno,
                    "col": node.col_offset,
                }
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if self._is_ignored(node):
            return
        if "CRP" in self.active_ops:
            val = node.value
            mutated_val: Any = None
            # Note: bool is a subclass of int in Python, so check bool first!
            if isinstance(val, bool):
                mutated_val = not val
            elif isinstance(val, int):
                mutated_val = val + 1
            elif isinstance(val, float):
                mutated_val = val + 1.0

            if mutated_val is not None:
                new_node = ast.Constant(value=mutated_val)
                ast.copy_location(new_node, node)
                replacement = ast.unparse(new_node)
                start_char, end_char = self._get_char_span(node)
                original = self.source[start_char:end_char]
                self.candidates.append(
                    {
                        "node": node,
                        "operator": "CRP",
                        "original": original,
                        "replacement": replacement,
                        "start_char": start_char,
                        "end_char": end_char,
                        "line": node.lineno,
                        "col": node.col_offset,
                    }
                )
        self.generic_visit(node)


def generate_mutants(
    path: str,
    source: str,
    *,
    operators: Sequence[str] = OPERATORS,
    max_mutants: int = 10_000,
) -> list[Mutant]:
    """Generate mutants for a given Python source code."""
    for op in operators:
        if op not in OPERATORS:
            raise MutationError("invalid_option", f"Invalid operator: {op}")

    if not source.strip():
        return []

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        raise MutationError("syntax_error", f"Syntax error: {e.msg}") from e

    lines = source.splitlines(keepends=True)
    lines_bytes = [line.encode("utf-8") for line in lines]
    line_offsets: list[int] = []
    curr = 0
    for line in lines:
        line_offsets.append(curr)
        curr += len(line)

    collector = _MutantCollector(path, source, set(operators), line_offsets, lines_bytes)
    collector.visit(tree)

    # Order: (line, col, operator)
    # Index is the position among mutants of the same node and operator
    candidates = collector.candidates
    candidates.sort(key=lambda c: (c["line"], c["col"], c["operator"]))

    if len(candidates) > max_mutants:
        raise MutationError(
            "too_many_mutants",
            f"Candidate mutants count {len(candidates)} exceeds maximum limit {max_mutants}",
        )

    # Assign indices
    node_op_counts: dict[tuple[int, str], int] = {}
    mutants: list[Mutant] = []
    for c in candidates:
        key = (id(c["node"]), c["operator"])
        idx = node_op_counts.get(key, 0)
        node_op_counts[key] = idx + 1
        mut_id = f"{path}:{c['line']}:{c['col']}:{c['operator']}:{idx}"
        mutants.append(
            Mutant(
                id=mut_id,
                path=path,
                line=c["line"],
                col=c["col"],
                operator=c["operator"],
                original=c["original"],
                replacement=c["replacement"],
                _source=source,
                _start_char=c["start_char"],
                _end_char=c["end_char"],
            )
        )
    return mutants


def run_mutants(
    mutants: Sequence[Mutant],
    runner: TestRunner,
    *,
    on_event: Callable[[MutantEvent], None] | None = None,
) -> Report:
    """Run tests for each mutant and summarize results."""
    if not mutants:
        return Report(results=(), score=None, survivors=())

    results: list[MutantResult] = []
    survivors: list[str] = []
    killed_count = 0
    timeout_count = 0
    error_count = 0

    for mutant in mutants:
        outcome: Outcome
        detail: str | None = None
        try:
            res = runner.run(mutant)
            if res not in ("killed", "survived", "timeout"):
                outcome = "error"
                detail = f"Unexpected runner return: {res}"
            else:
                outcome = res
        except Exception as e:
            outcome = "error"
            detail = type(e).__name__

        if outcome == "killed":
            killed_count += 1
        elif outcome == "timeout":
            timeout_count += 1
        elif outcome == "survived":
            survivors.append(mutant.id)
        elif outcome == "error":
            error_count += 1

        if on_event is not None:
            on_event(MutantEvent(id=mutant.id, outcome=outcome))

        results.append(MutantResult(id=mutant.id, outcome=outcome, detail=detail))

    total_valid = len(mutants) - error_count
    score = None if total_valid <= 0 else round((killed_count + timeout_count) / total_valid, 4)

    return Report(results=tuple(results), score=score, survivors=tuple(survivors))
