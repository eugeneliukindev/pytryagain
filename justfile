set shell := ["sh", "-c"]

export VIRTUAL_ENV := ".venv"

_default:
    @just --list --unsorted --list-heading $'Available commands…\n'


[doc("Ruff format + check")]
[group("linter")]
lint:
    uv run --group lint ruff format --check src/
    uv run --group lint ruff check src/

[doc("Mypy check")]
[group("static analysis")]
typecheck:
    uv run --group typing mypy src/

[doc("Run tests")]
[group("tests")]
test *args:
    uv run --group test pytest {{args}}

[doc("Run all checks")]
[group("infra")]
[parallel]
check: lint typecheck

[doc("Release a new version: just release patch|minor|major")]
[group("release")]
[confirm("Release to PyPI?")]
release bump="patch":
    uv run --group lint ruff check src/
    uv run --group typing mypy src/
    uv version --bump {{bump}}
    git add pyproject.toml
    git commit -m "chore: bump version to $(uv version --short)"
    git tag "v$(uv version --short)"
    git push && git push --tags
