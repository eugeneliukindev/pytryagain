import pytest
from pytest_mock import MockerFixture

from pytryagain._sentinel import _MISSING
from pytryagain._utils import _compute_deadline, _should_give_up


def test_compute_deadline_returns_none_for_sentinel() -> None:
    result = _compute_deadline(_MISSING)

    assert result is None


def test_compute_deadline_returns_monotonic_plus_timeout(mocker: MockerFixture) -> None:
    mocker.patch("pytryagain._utils.time.monotonic", return_value=100.0)

    result = _compute_deadline(30.0)

    assert result == 130.0


@pytest.mark.parametrize(
    "attempt,tries,monotonic_val,deadline,retry_if,expected",
    [
        pytest.param(3, 3, 0.0, None, _MISSING, True, id="tries-exhausted"),
        pytest.param(1, 3, 200.0, 100.0, _MISSING, True, id="timed-out"),
        pytest.param(1, 3, 0.0, 100.0, _MISSING, False, id="not-timed-out"),
        pytest.param(1, 3, 0.0, None, lambda e: False, True, id="retry-if-false"),
        pytest.param(1, 3, 0.0, None, lambda e: True, False, id="retry-if-true"),
        pytest.param(1, 3, 0.0, None, _MISSING, False, id="no-conditions-met"),
    ],
)
def test_should_give_up(
    mocker: MockerFixture,
    attempt: int,
    tries: int,
    monotonic_val: float,
    deadline: float | None,
    retry_if: object,
    expected: bool,
) -> None:
    mocker.patch("pytryagain._utils.time.monotonic", return_value=monotonic_val)

    result = _should_give_up(attempt, tries, deadline, retry_if, ValueError("test"))  # type: ignore[arg-type]

    assert result is expected
