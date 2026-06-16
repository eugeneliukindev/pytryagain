import time
from typing import cast

from pytryagain._sentinel import _MISSING, _Sentinel
from pytryagain._types import (
    AnyExceptionCallback,
    AsyncExceptionCallback,
    RetryIfException,
    RetryIfResult,
    SyncExceptionCallback,
)


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


def _should_accept_result(
    retry_if_result: RetryIfResult | _Sentinel,
    result: object,
    attempt: int,
    tries: int,
    deadline: float | None,
) -> bool:
    return (
        retry_if_result is _MISSING
        or not cast("RetryIfResult", retry_if_result)(result)
        or attempt >= tries
        or _is_timed_out(deadline)
    )


def _invoke_sync_callback(
    callback: AnyExceptionCallback | _Sentinel,
    exc: BaseException,
    attempt: int,
) -> None:
    if callback is not _MISSING:
        cast("SyncExceptionCallback", callback)(exc, attempt)


async def _invoke_async_callback(
    callback: AnyExceptionCallback | _Sentinel,
    exc: BaseException,
    attempt: int,
    *,
    is_async: bool,
) -> None:
    if callback is not _MISSING:
        if is_async:
            await cast("AsyncExceptionCallback", callback)(exc, attempt)
        else:
            cast("SyncExceptionCallback", callback)(exc, attempt)
