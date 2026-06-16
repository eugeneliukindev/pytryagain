import time

from pytryagain._sentinel import _Sentinel
from pytryagain._types import RetryPredicate


def _compute_deadline(timeout: float | _Sentinel) -> float | None:
    return None if isinstance(timeout, _Sentinel) else time.monotonic() + timeout


def _should_give_up(
    attempt: int,
    tries: int,
    deadline: float | None,
    retry_if: RetryPredicate | _Sentinel,
    exc: BaseException,
) -> bool:
    timed_out = deadline is not None and time.monotonic() >= deadline
    return attempt >= tries or timed_out or (not isinstance(retry_if, _Sentinel) and not retry_if(exc))
