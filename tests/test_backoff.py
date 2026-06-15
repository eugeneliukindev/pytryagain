import pytest

from pytryagain.backoff import (
    ConstantBackoff,
    DecorrelatedJitterBackoff,
    EqualJitterBackoff,
    ExponentialBackoff,
    ExponentialJitterBackoff,
    FibonacciBackoff,
    FullJitterBackoff,
    LinearBackoff,
    TruncatedExponentialBackoff,
)


class TestDeterministicBackoff:
    @pytest.mark.parametrize(
        ("backoff", "attempt", "expected"),
        [
            pytest.param(ConstantBackoff(delay=2.0), 1, 2.0, id="constant-attempt-1"),
            pytest.param(ConstantBackoff(delay=2.0), 5, 2.0, id="constant-attempt-5"),
            pytest.param(LinearBackoff(base=1.0), 1, 1.0, id="linear-attempt-1"),
            pytest.param(LinearBackoff(base=2.0), 3, 6.0, id="linear-attempt-3"),
            pytest.param(ExponentialBackoff(base=2.0, initial=1.0), 1, 2.0, id="exponential-attempt-1"),
            pytest.param(ExponentialBackoff(base=2.0, initial=1.0), 3, 8.0, id="exponential-attempt-3"),
            pytest.param(FibonacciBackoff(base=1.0), 1, 1.0, id="fibonacci-attempt-1"),
            pytest.param(FibonacciBackoff(base=1.0), 5, 5.0, id="fibonacci-attempt-5"),
            pytest.param(
                TruncatedExponentialBackoff(base=2.0, initial=1.0, cap=100.0), 3, 8.0, id="truncated-under-cap"
            ),
            pytest.param(TruncatedExponentialBackoff(base=2.0, initial=1.0, cap=5.0), 3, 5.0, id="truncated-at-cap"),
        ],
    )
    def test_returns_expected_delay(self, backoff: object, attempt: int, expected: float) -> None:
        result = backoff(attempt)  # type: ignore[operator]

        assert result == expected


class TestJitterBackoff:
    @pytest.mark.parametrize(
        ("backoff", "attempt", "low", "high"),
        [
            pytest.param(ExponentialJitterBackoff(base=2.0, initial=1.0), 3, 0.0, 8.0, id="exp-jitter"),
            pytest.param(FullJitterBackoff(cap=60.0, base=2.0), 3, 0.0, 8.0, id="full-jitter"),
            pytest.param(EqualJitterBackoff(cap=60.0, base=2.0), 3, 4.0, 8.0, id="equal-jitter"),
        ],
    )
    def test_delay_within_range(self, backoff: object, attempt: int, low: float, high: float) -> None:
        result = backoff(attempt)  # type: ignore[operator]

        assert low <= result <= high


class TestDecorrelatedJitterBackoff:
    def test_updates_state_between_calls(self) -> None:
        backoff = DecorrelatedJitterBackoff(base=1.0, cap=60.0, prev_sleep=1.0)

        first = backoff(1)
        second = backoff(2)

        assert 0 < first <= 60.0
        assert 0 < second <= 60.0
        assert backoff.prev_sleep == second
