# Architecture

`mutation-lite` is a pure Python library designed for embeddability, relying only on the standard library (`ast`, `subprocess`, `tempfile`).

## Components

- **Mutant Generator**: Uses the standard `ast` module to analyze code. It converts character positions to span-exact byte offsets to correctly mutate multi-byte character sources. It skips docstrings, type annotations, decorators, f-string internals, and lines containing `# pragma: no mutate`.
- **Operator Suite**: Implements seven operators:
  - **AOR**: BinOp swap (+/-, */%, etc.).
  - **ROR**: Comparison swap (<, <=, >, >=, ==, !=, is/is not, in/not in).
  - **LCR**: Logical swap (and/or).
  - **UOI**: Unary operator removal (not).
  - **CRP**: Constant replacement (int n+1, bool flip, float +1.0).
  - **RET**: Replace `return <expr>` with `return None`.
  - **SDL**: Remove expression statement calls with `pass`.
- **Execution Engine**: The `run_mutants` function consumes a `TestRunner` protocol implementation. The `SubprocessRunner` creates a temporary directory, copies the target root, applies the mutation to the specific file, and runs a provided command line.