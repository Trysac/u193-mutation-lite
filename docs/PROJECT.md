# Project record

## Objective

To provide lightweight, deterministic AST-based mutation testing for Python, enabling teams to perform rapid validation of critical modules without the overhead of heavyweight frameworks.

## Scope

- **In-scope**: The public API (including `generate_mutants`, `Mutant`, `TestRunner`, `run_mutants`, `Report`, and `SubprocessRunner`), complete type annotations, and unit tests ensuring adherence to the mutation logic specifications.
- **Out-of-scope**: Equivalent-mutant detection, coverage-guided mutation selection, parallel mutant execution, caching mechanisms, and support for languages other than Python.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository initialized from the factory template. |

## Effort metrics

| Metric | Value |
|---|---|
| Tokens (input / output) | 1163631 / 19755 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.2865 |

## Factory run u193 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | gemini-3.8-flash | yes | 4391 | 12891 | 0 | 0 | 0.0258 |
| fix-1 | gemini-3.8-flash | no | 39135 | 689 | 0 | 100106 | 0.0394 |
| fix-2 | gemini-3.8-flash | no | 25861 | 892 | 0 | 60992 | 0.0273 |
| fix-3 | gemini-3.8-flash | no | 15542 | 224 | 0 | 11220 | 0.0133 |
| fix-4 | gemini-3.8-flash | no | 84645 | 1302 | 0 | 523419 | 0.1076 |
| audit | gemini-3.1-flash-lite | no | 45060 | 900 | 0 | 63156 | 0.0142 |
| fix-1 | gemini-3.8-flash | no | 18313 | 804 | 0 | 23153 | 0.0185 |
| docs | gemini-3.1-flash-lite | no | 148638 | 2053 | 0 | 0 | 0.0402 |

Total: $0.2865. Prices: Anthropic list prices.
