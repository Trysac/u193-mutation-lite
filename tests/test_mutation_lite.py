"""Comprehensive tests for mutation_lite."""

import ast
import sys
from pathlib import Path
from typing import Any, Literal

import pytest

from mutation_lite import (
    Mutant,
    MutantEvent,
    MutationError,
    SubprocessRunner,
    generate_mutants,
    run_mutants,
)
from mutation_lite.__main__ import main


class FakeRunner:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def run(self, mutant: Mutant) -> Literal["killed", "survived", "timeout"]:
        val = self.mapping.get(mutant.id, "survived")
        if val == "raise":
            raise ValueError("Runner failed")
        return val  # type: ignore[return-value]


def test_acceptance_1() -> None:
    # generate_mutants('m.py', 'def f(a, b):\n    return a + b\n') returns ids ['m.py:2:4:RET:0', 'm.py:2:11:AOR:0'],
    # and the AOR mutant's mutated_source() == 'def f(a, b):\n    return a - b\n' while the RET mutant's is 'def f(a, b):\n    return None\n'
    src = "def f(a, b):\n    return a + b\n"
    mutants = generate_mutants("m.py", src)
    ids = [m.id for m in mutants]
    assert ids == ["m.py:2:4:RET:0", "m.py:2:11:AOR:0"]
    aor = next(m for m in mutants if m.operator == "AOR")
    ret = next(m for m in mutants if m.operator == "RET")
    assert aor.mutated_source() == "def f(a, b):\n    return a - b\n"
    assert ret.mutated_source() == "def f(a, b):\n    return None\n"


def test_acceptance_2() -> None:
    # 'x < 1' yields one ROR mutant 'x <= 1', '<=' yields '<', '==' yields '!=' and
    # the chained 'a < b < c' yields 2 ROR mutants; 'a and b' yields LCR 'a or b' and 'not x' yields UOI 'x'
    muts = [
        m for m in generate_mutants("t.py", "x < 1") if m.operator == "ROR"
    ]  # '1' also yields CRP
    assert len(muts) == 1
    assert muts[0].replacement == "x <= 1"

    muts = [
        m for m in generate_mutants("t.py", "x <= 1") if m.operator == "ROR"
    ]  # '1' also yields CRP
    assert len(muts) == 1
    assert muts[0].replacement == "x < 1"

    muts = [
        m for m in generate_mutants("t.py", "x == 1") if m.operator == "ROR"
    ]  # '1' also yields CRP
    assert len(muts) == 1
    assert muts[0].replacement == "x != 1"

    # chained
    muts = generate_mutants("t.py", "a < b < c")
    assert len(muts) == 2
    assert [m.operator for m in muts] == ["ROR", "ROR"]
    assert [m.replacement for m in muts] == ["a <= b < c", "a < b <= c"]

    # LCR
    muts = generate_mutants("t.py", "a and b")
    assert len(muts) == 1
    assert muts[0].operator == "LCR"
    assert muts[0].replacement == "a or b"

    # UOI
    muts = generate_mutants("t.py", "not x")
    assert len(muts) == 1
    assert muts[0].operator == "UOI"
    assert muts[0].replacement == "x"


def test_acceptance_3() -> None:
    # CRP turns '0' into '1' and 'True' into 'False', never mutates string constants, docstrings
    # or annotations ('x: int = 5' gives only '5' -> '6'), and 'return None' yields no RET mutant
    muts = generate_mutants("t.py", "0")
    assert len(muts) == 1
    assert muts[0].operator == "CRP"
    assert muts[0].replacement == "1"

    muts = generate_mutants("t.py", "True")
    assert len(muts) == 1
    assert muts[0].operator == "CRP"
    assert muts[0].replacement == "False"

    # string constants
    muts = generate_mutants("t.py", '"hello"')
    assert len(muts) == 0

    # docstring
    doc_src = '"""Module docstring."""\ndef f():\n    """Func doc."""\n    pass\n'
    assert generate_mutants("t.py", doc_src) == []

    # annotation 'x: int = 5' gives only '5' -> '6'
    muts = generate_mutants("t.py", "x: int = 5")
    assert len(muts) == 1
    assert muts[0].operator == "CRP"
    assert muts[0].original == "5"
    assert muts[0].replacement == "6"

    # return None yields no RET mutant
    muts = generate_mutants("t.py", "return None")
    assert len(muts) == 0


def test_acceptance_4() -> None:
    # A line ending with '# pragma: no mutate' yields no mutants, and 's = "é"; y = a + b' yields
    # an AOR mutant whose mutated source contains 'a - b' with 'é' intact (ast byte offsets converted to str indexes)
    src_pragma = "a = b + c  # pragma: no mutate\n"
    assert generate_mutants("t.py", src_pragma) == []

    src_unicode = 's = "é"; y = a + b'
    muts = generate_mutants("t.py", src_unicode)
    assert len(muts) == 1
    assert muts[0].operator == "AOR"
    mutated = muts[0].mutated_source()
    assert 's = "é"; y = a - b' in mutated
    assert "é" in mutated


def test_acceptance_5() -> None:
    # run_mutants(mutants, FakeRunner({'m.py:2:11:AOR:0': 'killed', 'm.py:2:4:RET:0': 'survived'}))
    # returns score 0.5 and survivors ['m.py:2:4:RET:0']; a runner raising ValueError records outcome
    # 'error' with detail 'ValueError', excluded from the score; 'timeout' counts as killed
    muts = generate_mutants("m.py", "def f(a, b):\n    return a + b\n")
    runner = FakeRunner({"m.py:2:11:AOR:0": "killed", "m.py:2:4:RET:0": "survived"})
    rep = run_mutants(muts, runner)  # type: ignore[arg-type]
    assert rep.score == 0.5
    assert list(rep.survivors) == ["m.py:2:4:RET:0"]

    # timeout counts as killed
    runner_to = FakeRunner({"m.py:2:11:AOR:0": "timeout", "m.py:2:4:RET:0": "survived"})
    rep_to = run_mutants(muts, runner_to)  # type: ignore[arg-type]
    assert rep_to.score == 0.5

    # error excluded from score
    runner_err = FakeRunner({"m.py:2:11:AOR:0": "killed", "m.py:2:4:RET:0": "raise"})
    rep_err = run_mutants(muts, runner_err)  # type: ignore[arg-type]
    assert rep_err.score == 1.0  # 1 killed out of 1 valid
    assert rep_err.results[0].outcome == "error"
    assert rep_err.results[0].detail == "ValueError"


def test_acceptance_6() -> None:
    # Every mutant's mutated_source() parses with ast.parse; a source with a syntax error raises
    # MutationError with code 'syntax_error'; max_mutants=1 with two candidates raises code 'too_many_mutants';
    # operators=('XYZ',) raises code 'invalid_option'
    src = "def f(a, b):\n    return a + b\n"
    muts = generate_mutants("m.py", src)
    for m in muts:
        parsed = ast.parse(m.mutated_source())
        assert parsed is not None

    with pytest.raises(MutationError) as exc_syntax:
        generate_mutants("bad.py", "def f(")
    assert exc_syntax.value.code == "syntax_error"

    with pytest.raises(MutationError) as exc_max:
        generate_mutants("m.py", src, max_mutants=1)
    assert exc_max.value.code == "too_many_mutants"

    with pytest.raises(MutationError) as exc_opt:
        generate_mutants("m.py", src, operators=("XYZ",))
    assert exc_opt.value.code == "invalid_option"


def test_acceptance_7() -> None:
    # on_event receives MutantEvent(id, outcome) per mutant and never the mutated source;
    # generate_mutants('e.py', '') == [] and run_mutants([], runner).score is None
    events: list[MutantEvent] = []
    muts = generate_mutants("m.py", "def f(a, b):\n    return a + b\n")
    runner = FakeRunner({"m.py:2:11:AOR:0": "killed", "m.py:2:4:RET:0": "survived"})
    run_mutants(muts, runner, on_event=events.append)  # type: ignore[arg-type]
    assert len(events) == 2
    assert events[0] == MutantEvent(id="m.py:2:4:RET:0", outcome="survived")
    assert events[1] == MutantEvent(id="m.py:2:11:AOR:0", outcome="killed")
    # check MutantEvent has no source attribute
    assert not hasattr(events[0], "mutated_source")
    assert not hasattr(events[0], "source")

    assert generate_mutants("e.py", "") == []
    assert run_mutants([], runner).score is None  # type: ignore[arg-type]


def test_acceptance_8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # CLI: main(['list', 'm.py']) prints 'm.py:2:4:RET:0 return a + b -> return None' and
    # 'm.py:2:11:AOR:0 a + b -> a - b' and returns 0; a file with a syntax error returns 2
    m_file = tmp_path / "m.py"
    m_file.write_text("def f(a, b):\n    return a + b\n", encoding="utf-8")

    ret = main(["list", str(m_file)])
    captured = capsys.readouterr().out
    assert ret == 0
    assert f"{m_file!s}:2:4:RET:0 return a + b -> return None" in captured
    assert f"{m_file!s}:2:11:AOR:0 a + b -> a - b" in captured

    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(", encoding="utf-8")
    assert main(["list", str(bad_file)]) == 2


def test_operators_coverage() -> None:
    # Exercise remaining operators: BinOps (*, /, //, %), ROR (> >= != is is not in not in),
    # BoolOp (or -> and), SDL (call expr), CRP (float, False)
    src = """class A:\n    '''Class doc.'''\n    def method(self, x: float = 1.5) -> int:\n        x = x * 2.0\n        y = x / 3\n        z = y // 4\n        w = z % 5\n        flag = False\n        if x > 1 and x >= 2 or x != 3 or x is None or x is not 1 or x in [1] or x not in [2]:\n            print('test')\n        return 10\n"""
    muts = generate_mutants("ops.py", src)
    ops = {m.operator for m in muts}
    assert "AOR" in ops
    assert "ROR" in ops
    assert "LCR" in ops
    assert "CRP" in ops
    assert "RET" in ops
    assert "SDL" in ops

    sdl_mut = next(m for m in muts if m.operator == "SDL")
    assert sdl_mut.replacement == "pass"
    assert "pass" in sdl_mut.mutated_source()


def test_fstring_and_annotated_func() -> None:
    src = """async def f(a: int = 1, *args: int, kw: int = 2, **kwargs: str) -> None:\n    s = f'{a + b}'\n    return None\n"""
    muts = generate_mutants("fn.py", src)
    # f-string internals should not be mutated
    aor_muts = [m for m in muts if m.operator == "AOR"]
    assert len(aor_muts) == 0


def test_edge_cases_crlf_tabs_nested() -> None:
    src = (
        "def outer():\r\n\tdef inner():\r\n\t\treturn (lambda x: x + 1)(2)\r\n\treturn inner()\r\n"
    )
    muts = generate_mutants("nested.py", src)
    assert len(muts) > 0
    for m in muts:
        ast.parse(m.mutated_source())


def test_subprocess_runner_real(tmp_path: Path) -> None:
    # SubprocessRunner exercised with sys.executable -c bound within 20s
    root = tmp_path / "proj"
    root.mkdir()
    target = root / "code.py"
    target.write_text("def calc():\n    return 1 + 2\n", encoding="utf-8")

    # Test script will exit 1 if calc() != 3
    test_cmd = [
        sys.executable,
        "-c",
        "import code; sys.exit(0 if code.calc() == 3 else 1)",
    ]
    runner = SubprocessRunner(test_cmd, root, timeout_s=20.0)

    muts = generate_mutants("code.py", target.read_text(encoding="utf-8"))
    aor = next(
        m for m in muts if m.operator == "AOR"
    )  # 1 - 2 -> calc() returns -1 -> exit 1 -> killed
    outcome = runner.run(aor)
    assert outcome == "killed"


def test_subprocess_runner_absolute_path_does_not_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "proj_abs"
    root.mkdir()
    target = root / "code.py"
    original_code = "def calc():\n    return 1 + 2\n"
    target.write_text(original_code, encoding="utf-8")

    test_cmd = [
        sys.executable,
        "-c",
        "import code; sys.exit(0 if code.calc() == 3 else 1)",
    ]
    runner = SubprocessRunner(test_cmd, root, timeout_s=20.0)

    # Mutant generated using absolute path
    muts = generate_mutants(str(target), original_code)
    aor = next(m for m in muts if m.operator == "AOR")
    outcome = runner.run(aor)
    assert outcome == "killed"
    # Ensure original source file was not overwritten
    assert target.read_text(encoding="utf-8") == original_code


def test_subprocess_runner_survived_and_timeout(tmp_path: Path) -> None:
    root = tmp_path / "proj2"
    root.mkdir()
    target = root / "code.py"
    target.write_text("x = 10\n", encoding="utf-8")
    muts = generate_mutants("code.py", target.read_text(encoding="utf-8"))

    # Command that always succeeds -> survived
    runner_ok = SubprocessRunner(
        [sys.executable, "-c", "import sys; sys.exit(0)"], root, timeout_s=20.0
    )
    assert runner_ok.run(muts[0]) == "survived"

    # Command that times out
    runner_timeout = SubprocessRunner(
        [sys.executable, "-c", "import time; time.sleep(1.0)"], root, timeout_s=0.1
    )
    assert runner_timeout.run(muts[0]) == "timeout"


def test_run_mutants_all_error() -> None:
    muts = generate_mutants("m.py", "x = 1 + 2")

    class FailingRunner:
        def run(self, mutant: Mutant) -> Literal["killed", "survived", "timeout"]:
            raise RuntimeError("boom")

    rep = run_mutants(muts, FailingRunner())  # type: ignore[arg-type]
    assert rep.score is None
    assert len(rep.results) > 0
    assert rep.results[0].outcome == "error"


def test_run_mutants_unexpected_return() -> None:
    muts = generate_mutants("m.py", "x = 1 + 2")

    class BadRunner:
        def run(self, mutant: Mutant) -> Any:
            return "unknown"

    rep = run_mutants(muts, BadRunner())  # type: ignore[arg-type]
    assert rep.results[0].outcome == "error"
    assert "Unexpected runner return" in (rep.results[0].detail or "")


def test_cli_run_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "mod.py"
    target.write_text("def f():\n    return 42\n", encoding="utf-8")

    # Run with command where mutant survives (command exits 0)
    ret = main(["run", str(target), "--root", str(root), "--", sys.executable, "-c", "exit(0)"])
    captured = capsys.readouterr().out
    assert ret == 1
    assert "Survivors:" in captured

    # Run with command where mutant is killed (command exits 1)
    ret_killed = main(
        ["run", str(target), "--root", str(root), "--", sys.executable, "-c", "exit(1)"]
    )
    captured_killed = capsys.readouterr().out
    assert ret_killed == 0
    assert "All mutants killed or timed out." in captured_killed

    # Missing file
    assert main(["run", "missing.py", "--root", str(root), "--", "echo"]) == 2

    # No command after --
    assert main(["run", str(target), "--root", str(root)]) == 2
