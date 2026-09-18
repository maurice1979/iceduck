# ADR-0012: Code style, docstrings, and typing standards

Status: Accepted
Date: 2026-09-18

## Context

Final polish pass before uploading the repo to GitHub. No lint/format/type-check tooling existed at all (confirmed — no `[tool.ruff]`/`[tool.mypy]`/`.flake8`/etc. anywhere), and an audit of all 18 Python files found no structured docstrings anywhere (all plain prose or missing entirely), and a handful of missing type-hint return annotations (7 CLI commands, 2 boto3-client factories).

## Decision

- **`ruff`** for linting and formatting: 120-character line length, import sorting, pyupgrade, pydocstyle (`convention = "numpy"`), and flake8-annotations (enforces type hints on public functions).
- **`mypy`** for actual type checking, with the `pydantic.mypy` plugin enabled (without it, `BaseSettings` subclasses whose fields are populated from the environment falsely report "missing named argument" at every call site — `Settings()` in particular) and `ignore_missing_imports` for third-party libraries with no available stubs (`kaggle`, `plotly`, `pyarrow` — `boto3`/`pyyaml`/`pandas` all have real stub packages, installed instead: `boto3-stubs[s3,glue]`, `types-PyYAML`, `pandas-stubs`).
- **NumPy-style docstrings + full type hints on core source only** (`src/iceduck/`, `dashboard/`, `scripts/`, `sample_data/`) — `tests/*` and `conftest.py` are exempted from the docstring/annotation rules (`ruff`'s `per-file-ignores`), matching standard pytest practice where test names are self-documenting.
- **ADR references don't belong in docstrings.** A docstring is a self-contained API contract (what a `help()` call or a Sphinx-generated page shows) — an internal ADR number isn't something an external reader has access to or benefits from. The 7 occurrences found in this codebase had their citations dropped while keeping the underlying explanation (e.g. "Floci has no Iceberg REST Catalog endpoint, so reads resolve a metadata pointer instead of a live ATTACH" stays; "(ADR-0007)" doesn't). ADR/plan references remain normal and encouraged in `docs/` prose itself, and in code comments where they help a maintainer find more context — this is specifically about docstrings.

## Consequences

- Two genuine (not stub-gap) type issues were found and fixed properly, not suppressed: `pyiceberg.catalog.load_catalog()`'s return type is the base `Catalog` (it can't be statically narrowed to `GlueCatalog`, since that depends on a runtime `type` string) — fixed with an explicit, documented `typing.cast`, not a blanket `# type: ignore`. And `pandas-stubs` couldn't statically prove `.groupby(..., as_index=False)["col"].sum()` returns a DataFrame (it does, at runtime, verified) — fixed by rewriting to named aggregation (`.agg(total_claim_cost=("total_claim_cost", "sum"))`), which is both unambiguous to the type checker and more idiomatic pandas, not a workaround.
- `make lint` / `make format` / `make typecheck` all pass clean as of this ADR; `make test` and `make test-integration` were re-run after every code change in this pass and confirm zero functional regressions from the docstring/type-hint/cast/groupby rewrites.
- Future code in `src/iceduck/`, `dashboard/`, `scripts/` needs NumPy docstrings and full type hints to pass `make lint`/`make typecheck` — this is now an enforced standard, not just a one-time cleanup.
