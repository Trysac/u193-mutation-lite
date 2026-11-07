# mutation-lite

[![PyPI version](https://img.shields.io/pypi/v/trysac-mutation-lite)](https://pypi.org/project/trysac-mutation-lite/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-mutation-lite)](LICENSE)
[![CI](https://github.com/Trysac/u193-mutation-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u193-mutation-lite/actions/workflows/ci.yml)

Lightweight ast-based mutation testing for Python: seven operators, stable mutant ids, span-exact source edits and a pluggable test runner

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-mutation-lite
# or
uv add trysac-mutation-lite
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import mutation_lite

# normalize() trims surrounding whitespace and lower-cases the text.
print(mutation_lite.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    mutation_lite.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
