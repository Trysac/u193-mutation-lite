# Security notes

## Threat model

`mutation-lite` is a pure Python library. It does not perform I/O beyond temporary file management and subprocess invocation.

### Defended

- **Untrusted Input**: The library relies on `ast.parse`. It does not use `eval()` or `exec()` on strings. Syntax errors are caught and raised as `MutationError('syntax_error', ...)`, ensuring bad code does not execute.
- **Supply Chain**: The project has zero runtime dependencies. Dependabot is enabled for weekly updates, and CI workflows are pinned to major versions with minimal permissions.
- **Leaked Secrets**: `gitleaks` is integrated into local gates and CI. `.env` files are ignored by git.

### Not Defended

- **Test Environment Security**: Since the library runs arbitrary test commands via `SubprocessRunner`, the execution environment is only as secure as the test command itself. Users should only run mutation tests in isolated containers or sandboxed environments.

## Publishing

Releases to PyPI utilize Trusted Publishing (OIDC). No long-lived credentials are stored in the repository.