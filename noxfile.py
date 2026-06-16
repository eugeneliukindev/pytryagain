from pathlib import Path

import nox

nox.options.default_venv_backend = "uv"

PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14", "3.15")


def _install(session: nox.Session, *groups: str) -> None:
    session.run_install(
        "uv",
        "sync",
        *(f"--group={g}" for g in groups),
        "--locked",
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    _install(session, "tests")
    session.log("Running pytest on Python %s", session.python)
    session.run("pytest", *session.posargs)


@nox.session
def lint(session: nox.Session) -> None:
    _install(session, "lint")
    session.log("Checking ruff format")
    session.run("ruff", "format", "--check", "src/")
    session.log("Running ruff lint")
    session.run("ruff", "check", "src/")


@nox.session
def typecheck(session: nox.Session) -> None:
    _install(session, "typecheck")
    session.log("Running mypy in strict mode")
    session.run("mypy", "src/")


@nox.session
def pre_commit(session: nox.Session) -> None:
    _install(session, "hooks")
    session.log("Running pre-commit hooks on all files")
    session.run("pre-commit", "run", "--all-files", "--show-diff-on-failure")


@nox.session
def pkg_meta(session: nox.Session) -> None:
    _install(session, "pkg-check")
    tmp_dir = Path(session.create_tmp())
    session.log("Building sdist and wheel")
    session.run("uv", "build", "--sdist", "--wheel", "--out-dir", str(tmp_dir), external=True)
    wheels = [str(p) for p in tmp_dir.glob("*.whl")]
    sdists = [str(p) for p in tmp_dir.glob("*.tar.gz")]
    session.log("Checking distribution metadata with twine")
    session.run("twine", "check", *wheels, *sdists)
    session.log("Checking wheel contents")
    session.run("check-wheel-contents", "--no-config", *wheels)
