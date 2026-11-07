# Stack

## Used

| Tool | Why |
|---|---|
| Python >= 3.10 | Enables modern type hinting syntax. |
| uv | Provides fast, reproducible dependency management and builds. |
| hatchling | Minimal, standards-compliant build backend. |
| ruff | Combines linting and formatting into one efficient utility. |
| mypy (strict) | Ensures type safety for the library and ships `py.typed`. |
| pytest + pytest-cov | Industry-standard test runner with branch coverage analysis. |
| gitleaks | Automates secret scanning in CI and locally. |
| GitHub Actions | Orchestrates testing and distribution pipelines. |

## Discarded

| Tool | Why not |
|---|---|
| Poetry | Slower; `uv` handles dependency groups and resolution more efficiently. |
| Black / Isort / Flake8 | Replaced by `ruff`, which offers identical features at higher speed. |
| Tox / Nox | Handled by `uv` and direct CI configuration. |
| Custom Shell Scripts | Non-portable; standard Python is used for all gate logic. |