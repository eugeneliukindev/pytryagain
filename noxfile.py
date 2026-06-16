from pathlib import Path

import nox

nox.needs_version = ">=2024.10"
nox.options.default_venv_backend = "uv"

_PYPROJECT = nox.project.load_toml("pyproject.toml")
PYTHON_VERSIONS = nox.project.python_versions(_PYPROJECT)


def _pre_commit_run(session: nox.Session, hook_id: str) -> None:
    session.run(
        "uv",
        "run",
        "--locked",
        "--group=hooks",
        "pre-commit",
        "run",
        hook_id,
        "--all-files",
        external=True,
    )


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    session.run_install(
        "uv",
        "sync",
        "--group=tests",
        "--locked",
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.log("Running pytest on Python %s", session.python)
    session.run("pytest", *session.posargs)


@nox.session(venv_backend="none")
def lint(session: nox.Session) -> None:
    session.log("Running ruff lint")
    _pre_commit_run(session, "ruff")
    session.log("Checking ruff format")
    _pre_commit_run(session, "ruff-format")


@nox.session(venv_backend="none")
def typecheck(session: nox.Session) -> None:
    session.log("Running mypy")
    _pre_commit_run(session, "mypy")


@nox.session(venv_backend="none")
def file_checks(session: nox.Session) -> None:
    session.log("Running pre-commit file-check hooks")
    session.run(
        "uv",
        "run",
        "--locked",
        "--group=hooks",
        "pre-commit",
        "run",
        "--all-files",
        "--show-diff-on-failure",
        external=True,
        env={"SKIP": "ruff,ruff-format,mypy"},
    )


@nox.session(venv_backend="none")
def pkg_meta(session: nox.Session) -> None:
    tmp_dir = Path(session.create_tmp())
    session.log("Building sdist and wheel")
    session.run("uv", "build", "--sdist", "--wheel", "--out-dir", str(tmp_dir), external=True)
    wheels = [str(p) for p in tmp_dir.glob("*.whl")]
    sdists = [str(p) for p in tmp_dir.glob("*.tar.gz")]
    session.log("Checking distribution metadata with twine")
    session.run("uv", "run", "--locked", "--group=pkg-check", "twine", "check", *wheels, *sdists, external=True)
    session.log("Checking wheel contents")
    session.run(
        "uv",
        "run",
        "--locked",
        "--group=pkg-check",
        "check-wheel-contents",
        "--no-config",
        *wheels,
        external=True,
    )
