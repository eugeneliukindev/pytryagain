import nox

nox.needs_version = ">=2024.10"
nox.options.default_venv_backend = "uv"

_PYPROJECT = nox.project.load_toml("pyproject.toml")
PYTHON_VERSIONS = nox.project.python_versions(_PYPROJECT)


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
