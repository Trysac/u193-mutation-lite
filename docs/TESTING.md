# Testing

## Coverage Policy

- Branch coverage must be at or above 80%. Failure to meet this threshold will block CI.
- Tests must be deterministic: no network usage, no wall-clock dependencies, and no reliance on execution order.
- Every bug fix must include a regression test that fails without the fix.

## Test Structure

Tests are located in `tests/` and mirror the package structure, primarily `test_mutation_lite.py`. They exercise:

- The public API: `generate_mutants` and `run_mutants`.
- Observable effects: return values, side effects, and exact exception handling.
- Edge cases: tabs, CRLF, nested functions, and empty files.

## Execution

```sh
uv run pytest --cov=mutation_lite
uv run python scripts/check.py
```