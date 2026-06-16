import time
from typing import cast

from pytryagain._types import AnyExceptionCallback, AsyncExceptionCallback, BackOffByException, ShouldRetry
from pytryagain.backoff import BackOff


def _always_retry(_: BaseException) -> bool:
    return True


def _noop_exception_callback(_exception: BaseException, _attempt: int) -> None:
    pass


def _get_backoff(
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException,
    exception: BaseException,
) -> BackOff:
    for exception_type, backoff in backoff_by_exception.items():
        if isinstance(exception, exception_type):
            return backoff
    return default_backoff


def _compute_deadline(timeout: float) -> float:
    return time.monotonic() + timeout


def _is_timed_out(deadline: float) -> bool:
    return time.monotonic() >= deadline


def _should_give_up(
    current_attempt: int,
    max_attempts: int,
    deadline: float,
    should_retry: ShouldRetry,
    exception: BaseException,
) -> bool:
    return current_attempt >= max_attempts or _is_timed_out(deadline) or not should_retry(exception)


async def _invoke_callback(
    callback: AnyExceptionCallback,
    exception: BaseException,
    attempt: int,
    *,
    is_async: bool,
) -> None:
    if is_async:
        await cast("AsyncExceptionCallback", callback)(exception, attempt)
    else:
        callback(exception, attempt)
