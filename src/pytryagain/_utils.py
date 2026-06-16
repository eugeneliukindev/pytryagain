import time
from typing import cast

from pytryagain._sentinel import _MISSING, _Sentinel
from pytryagain._types import RetryIfException


def _compute_deadline(timeout: float | _Sentinel) -> float | None:
    if timeout is _MISSING:
        return None
    return time.monotonic() + cast("float", timeout)


def _is_timed_out(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _should_give_up(
    attempt: int,
    tries: int,
    deadline: float | None,
    retry_if_exception: RetryIfException | _Sentinel,
    exc: BaseException,
) -> bool:
    predicate_stops = retry_if_exception is not _MISSING and not cast("RetryIfException", retry_if_exception)(exc)
    return attempt >= tries or _is_timed_out(deadline) or predicate_stops
