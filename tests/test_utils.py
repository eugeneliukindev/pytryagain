from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from pytryagain._types import ShouldRetry
from pytryagain._utils import _compute_deadline, _invoke_callback, _is_timed_out, _should_give_up


def test_compute_deadline_returns_monotonic_plus_timeout(mocker: MockerFixture) -> None:
    mocker.patch("pytryagain._utils.time.monotonic", return_value=100.0)

    result = _compute_deadline(30.0)

    assert result == 130.0


def test_compute_deadline_handles_no_timeout(mocker: MockerFixture) -> None:
    mocker.patch("pytryagain._utils.time.monotonic", return_value=100.0)

    result = _compute_deadline(float("inf"))

    assert result == float("inf")


@pytest.mark.parametrize(
    "monotonic_val,deadline,expected",
    [
        pytest.param(200.0, 100.0, True, id="timed-out"),
        pytest.param(100.0, 100.0, True, id="exactly-at-deadline"),
        pytest.param(0.0, 100.0, False, id="not-timed-out"),
        pytest.param(1_000_000.0, float("inf"), False, id="no-deadline-never-times-out"),
    ],
)
def test_is_timed_out(mocker: MockerFixture, monotonic_val: float, deadline: float, expected: bool) -> None:
    mocker.patch("pytryagain._utils.time.monotonic", return_value=monotonic_val)

    result = _is_timed_out(deadline)

    assert result is expected


@pytest.mark.parametrize(
    "current_attempt,max_attempts,monotonic_val,deadline,should_retry,expected",
    [
        pytest.param(3, 3, 0.0, float("inf"), lambda _: True, True, id="attempts-exhausted"),
        pytest.param(1, 3, 200.0, 100.0, lambda _: True, True, id="timed-out"),
        pytest.param(1, 3, 0.0, 100.0, lambda _: True, False, id="not-timed-out"),
        pytest.param(1, 3, 0.0, float("inf"), lambda _: False, True, id="retry-if-exception-false"),
        pytest.param(1, 3, 0.0, float("inf"), lambda _: True, False, id="retry-if-exception-true"),
    ],
)
def test_should_give_up(
    mocker: MockerFixture,
    current_attempt: int,
    max_attempts: int,
    monotonic_val: float,
    deadline: float,
    should_retry: ShouldRetry,
    expected: bool,
) -> None:
    mocker.patch("pytryagain._utils.time.monotonic", return_value=monotonic_val)

    result = _should_give_up(current_attempt, max_attempts, deadline, should_retry, ValueError("test"))

    assert result is expected


async def test_invoke_callback_calls_sync_callback() -> None:
    callback = MagicMock(return_value=None)

    await _invoke_callback(callback, ValueError("exc"), 1, is_async=False)

    callback.assert_called_once()


async def test_invoke_callback_awaits_async_callback() -> None:
    callback = AsyncMock(return_value=None)

    await _invoke_callback(callback, ValueError("exc"), 1, is_async=True)

    callback.assert_awaited_once()
