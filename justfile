set shell := ["sh", "-c"]

export VIRTUAL_ENV := ".venv"

_default:
    @just --list --unsorted --list-heading $'Available commands…\n'


# — linting ——————————————————————————————————————————————————————————————————

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
[group("linter")]
typecheck:
    uv run --locked --group typecheck mypy

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

[doc("Clean, build, and validate package")]
[group("build")]
pkg_meta: clean build check_build


# — infra ————————————————————————————————————————————————————————————————————

[doc("Run all CI checks locally")]
[group("infra")]
ci: lint typecheck file_checks pkg_meta test

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
