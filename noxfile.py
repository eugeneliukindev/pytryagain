from pathlib import Path

import nox

nox.options.default_venv_backend = "uv"

PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14", "3.15")


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
    session.log("Checking ruff format")
    session.run("uv", "run", "--locked", "--group=lint", "ruff", "format", "--check", "src/", external=True)
    session.log("Running ruff lint")
    session.run("uv", "run", "--locked", "--group=lint", "ruff", "check", "src/", external=True)


@nox.session(venv_backend="none")
def typecheck(session: nox.Session) -> None:
    session.log("Running mypy in strict mode")
    session.run("uv", "run", "--locked", "--group=typecheck", "mypy", external=True)


@nox.session(venv_backend="none")
def pre_commit(session: nox.Session) -> None:
    # ruff, ruff-format and mypy are skipped here because they run as dedicated nox sessions (lint, typecheck)
    session.log("Running pre-commit file-check hooks on all files")
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
        "uv", "run", "--locked", "--group=pkg-check", "check-wheel-contents", "--no-config", *wheels, external=True
    )
