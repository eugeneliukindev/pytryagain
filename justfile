set shell := ["sh", "-c"]

export VIRTUAL_ENV := ".venv"

_default:
    @just --list --unsorted --list-heading $'Available commands…\n'


[doc("Format and auto-fix with ruff")]
[group("linter")]
fmt:
    uv run --locked --group lint ruff format
    uv run --locked --group lint ruff check --fix

[doc("Check lint and format (no auto-fix)")]
[group("linter")]
lint:
    uv run --locked --group lint ruff format --check
    uv run --locked --group lint ruff check

[doc("Mypy check")]
[group("static analysis")]
typecheck:
    uv run --locked --group typecheck mypy

[doc("Run pre-commit file checks (excludes ruff and mypy)")]
[group("linter")]
file_checks:
    SKIP=ruff,ruff-format,mypy uv run --locked --group hooks pre-commit run --all-files --show-diff-on-failure

[doc("Build and validate package metadata")]
[group("infra")]
pkg_meta:
    #!/usr/bin/env sh
    tmp=$(mktemp -d)
    uv build --sdist --wheel --out-dir "$tmp"
    uv run --locked --group pkg-check twine check "$tmp"/*.whl "$tmp"/*.tar.gz
    uv run --locked --group pkg-check check-wheel-contents --no-config "$tmp"/*.whl
    rm -rf "$tmp"

[doc("Run tests")]
[group("tests")]
test *args:
    uv run --locked --group tests pytest {{args}}

[doc("Run tests across Python 3.10–3.15 via nox")]
[group("tests")]
nox *args:
    uv run --locked --group nox nox {{args}}

[doc("Run all CI checks locally")]
[group("infra")]
ci: lint typecheck file_checks pkg_meta test

[doc("Release a new version: just release patch|minor|major")]
[group("release")]
[confirm("Release to PyPI?")]
release bump="patch":
    just lint
    just typecheck
    uv version --bump {{bump}}
    git add pyproject.toml uv.lock
    git commit -m "chore: bump version to $(uv version --short)"
    git tag "v$(uv version --short)"
    git push && git push --tags
