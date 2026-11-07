# mutation-lite

Lightweight, deterministic AST-based mutation testing for Python. It provides seven operators, stable mutant identifiers, span-exact source edits, and a pluggable test runner.

## Problem

Line coverage only confirms code was executed, not that tests would detect logic errors within it. Existing mutation testing tools are often slow, configuration-heavy, and difficult to embed. Teams need a fast, reliable method to verify critical modules without the overhead of heavy external frameworks.

## Installation

```bash
pip install trysac-mutation-lite
```

## Usage

```python
from mutation_lite import generate_mutants

code = "def add(a, b):\n    return a + b\n"
mutants = generate_mutants("math.py", code)
for m in mutants:
    print(m.id, m.mutated_source())
```

## API Summary

- **generate_mutants(path: str, source: str, *, operators=..., max_mutants=10000) -> list[Mutant]**: Generates stable, deterministic mutants.
- **Mutant**: Frozen dataclass representing a code span mutation. Use `mutated_source()` to get the altered string.
- **TestRunner**: Protocol for custom test execution. `SubprocessRunner` is provided as a default implementation.
- **run_mutants(mutants, runner, *, on_event=None) -> Report**: Executes the test suite against generated mutants.
- **Report**: Summary of outcomes (`killed`, `survived`, `timeout`, `error`).
- **MutationError**: Raised for `syntax_error`, `too_many_mutants`, or `invalid_option`.

## Why not <best-known alternative>?

Unlike `mutmut`, `mutation-lite` is designed specifically as an embeddable library. It supports an injected runner interface, produces stable mutant IDs (deterministic based on `(line, col, operator, index)`), and handles UTF-8 source edits without external configuration.

## Security

See [docs/SECURITY.md](docs/SECURITY.md).