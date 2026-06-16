# Single source of truth for all checks: pre-commit hooks and CI jobs both delegate here,
# so tool flags and behaviour are always in sync across local commits and the pipeline.

set shell := ["sh", "-c"]

export VIRTUAL_ENV := ".venv"

_default:
    @just --list --unsorted --list-heading $'Available commands…\n'


# — linting ——————————————————————————————————————————————————————————————————

[doc("Auto-format with ruff")]
[group("linter")]
format:
    uv run --locked --group lint ruff format

[doc("Lint and auto-fix with ruff")]
[group("linter")]
fix:
    uv run --locked --group lint ruff check --fix

[doc("Format + fix (local dev shortcut)")]
[group("linter")]
check: format fix

[doc("Check lint and format without modifications (CI)")]
[group("linter")]
lint:
    uv run --locked --group lint ruff format --check
    uv run --locked --group lint ruff check

[doc("Mypy check")]
[group("linter")]
typecheck:
    uv run --locked --group typecheck mypy

[doc("Check single commit message (used by pre-commit commit-msg hook)")]
[group("linter")]
commitizen msg_file:
    uv run --locked --group hooks cz check --commit-msg-file {{msg_file}}

[doc("Check commits in range follow Conventional Commits")]
[group("linter")]
check-commits range="origin/main..HEAD":
    uv run --locked --group hooks cz check --rev-range {{range}}

[doc("Run pre-commit file checks (excludes ruff and mypy)")]
[group("linter")]
file_checks:
    SKIP=ruff,ruff-format,mypy uv run --locked --group hooks pre-commit run --all-files --show-diff-on-failure


# — tests ————————————————————————————————————————————————————————————————————

[doc("Run tests")]
[group("tests")]
test *args:
    uv run --locked --group tests pytest {{args}}

alias tests := test

[doc("Run tests across Python 3.10–3.15 via nox")]
[group("tests")]
nox *args:
    uv run --locked --group nox nox {{args}}


# — build ————————————————————————————————————————————————————————————————————

[doc("Remove build artifacts")]
[group("build")]
clean:
    rm -rf dist/

[doc("Build sdist and wheel into dist/")]
[group("build")]
build:
    uv build --sdist --wheel --out-dir dist/

[doc("Validate package metadata and wheel contents")]
[group("build")]
check_build:
    uv run --locked --group pkg-check twine check dist/*.whl dist/*.tar.gz
    uv run --locked --group pkg-check check-wheel-contents --no-config dist/*.whl

[doc("Clean, build, validate, and clean package")]
[group("build")]
pkg_meta:
    just clean
    just build
    just check_build
    just clean


# — infra ————————————————————————————————————————————————————————————————————

[doc("Run all CI checks locally")]
[group("ci")]
[parallel]
ci: lint typecheck file_checks check-commits pkg_meta nox

[doc("Release a new version: just release patch|minor|major")]
[group("infra")]
[confirm("Release to PyPI?")]
release bump="patch":
    uv version --bump {{bump}}
    just build
    git add pyproject.toml uv.lock
    git commit -m "chore: bump version to $(uv version --short)"
    git tag "v$(uv version --short)"
    git push && git push --tags
    just clean
