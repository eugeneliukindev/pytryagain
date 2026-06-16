import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from functools import partial, wraps
from typing import Any, ParamSpec, TypeVar, cast, overload

from ._sentinel import _MISSING, _Sentinel
from ._types import (
    AnyExceptionCallback,
    AsyncExceptionCallback,
    BackOffByException,
    RetryIfException,
    RetryIfResult,
    SyncExceptionCallback,
)
from ._utils import _compute_deadline, _is_timed_out, _should_give_up
from ._validators import _validate_retry_params
from .backoff import BackOff, ExponentialJitterBackoff

_P = ParamSpec("_P")
_T = TypeVar("_T")

_DEFAULT_BACKOFF: BackOff = ExponentialJitterBackoff()


def _get_backoff(
    default_backoff: BackOff, backoff_by_exception: BackOffByException | _Sentinel, exc: BaseException
) -> BackOff:
    if backoff_by_exception is _MISSING:
        return default_backoff
    for exc_type, backoff in cast("BackOffByException", backoff_by_exception).items():
        if isinstance(exc, exc_type):
            return backoff
    return default_backoff


@overload
def retry(
    func: Callable[_P, Awaitable[_T]],
    tries: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float | _Sentinel,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | _Sentinel,
    retry_if_exception: RetryIfException | _Sentinel,
    retry_if_result: RetryIfResult | _Sentinel,
    on_exception_callback: AnyExceptionCallback | _Sentinel,
    on_giveup_callback: AnyExceptionCallback | _Sentinel,
) -> Callable[_P, Awaitable[_T]]: ...


@overload
def retry(
    func: _Sentinel,
    tries: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float | _Sentinel,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | _Sentinel,
    retry_if_exception: RetryIfException | _Sentinel,
    retry_if_result: RetryIfResult | _Sentinel,
    on_exception_callback: AnyExceptionCallback | _Sentinel,
    on_giveup_callback: AnyExceptionCallback | _Sentinel,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]: ...


@overload
def retry(
    func: Callable[_P, _T],
    tries: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float | _Sentinel,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | _Sentinel,
    retry_if_exception: RetryIfException | _Sentinel,
    retry_if_result: RetryIfResult | _Sentinel,
    on_exception_callback: SyncExceptionCallback | _Sentinel,
    on_giveup_callback: SyncExceptionCallback | _Sentinel,
) -> Callable[_P, _T]: ...


def retry(
    func: Callable[_P, _T] | _Sentinel = _MISSING,
    tries: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    timeout: float | _Sentinel = _MISSING,
    default_backoff: BackOff = _DEFAULT_BACKOFF,
    backoff_by_exception: BackOffByException | _Sentinel = _MISSING,
    retry_if_exception: RetryIfException | _Sentinel = _MISSING,
    retry_if_result: RetryIfResult | _Sentinel = _MISSING,
    on_exception_callback: AnyExceptionCallback | _Sentinel = _MISSING,
    on_giveup_callback: AnyExceptionCallback | _Sentinel = _MISSING,
) -> Callable[_P, _T] | Callable[_P, Awaitable[_T]]:
    """Decorator that retries a function on exception or unsatisfactory result.

    Supports both sync and async functions. Can be used as a plain decorator
    ``@retry`` or as a decorator factory ``@retry(tries=5)``.

    Args:
        func: The function to wrap. When omitted, returns a partially applied
            decorator (decorator factory mode).
        tries: Total number of attempts, including the first call. ``tries=1``
            means no retries. Must be >= 1.
        exceptions: Tuple of exception types that trigger a retry. Any other
            exception propagates immediately without retrying.
        timeout: Total time budget in seconds across all attempts. Once elapsed,
            the current exception is re-raised without further retries.
        default_backoff: Delay strategy between attempts. Receives the current attempt
            number (1-based) and returns the sleep duration in seconds.
        backoff_by_exception: Per-exception-type delay overrides. Keys are
            BaseException subclasses; the first matching key wins. Falls back to
            ``default_backoff`` when no key matches.
        retry_if_exception: Predicate called with the caught exception. Return ``True``
            to retry, ``False`` to re-raise immediately (after calling
            ``on_giveup_callback``). When omitted, all matching exceptions retry.
        retry_if_result: Predicate called with the return value of a successful call.
            Return ``True`` to retry the call, ``False`` to accept the result. When
            tries are exhausted under this predicate, the last result is returned.
        on_exception_callback: Called after each failed attempt except the last.
            Receives the exception and the 1-based attempt number. For async
            functions, both sync and async callbacks are accepted. For sync
            functions, only a sync callback is allowed.
        on_giveup_callback: Called once when all attempts are exhausted or a
            retry is aborted by ``retry_if_exception``, before re-raising the exception.
            Same sync/async rules as ``on_exception_callback``.

    Returns:
        The wrapped function preserving the original signature, or a partially
        applied decorator when ``func`` is not provided.

    Raises:
        TypeError: If any parameter has an incorrect type, or if an async callback
            is passed for a sync function.
        ValueError: If ``tries`` < 1, ``timeout`` <= 0, or ``exceptions`` is empty.
        BaseException: The original exception after all attempts are exhausted,
            timeout is exceeded, or ``retry_if_exception`` returns ``False``.

    See also: https://github.com/eugeneliukindev/pytryagain/blob/main/README.md#examples
    """

    _validate_retry_params(
        tries,
        exceptions,
        timeout,
        default_backoff,
        backoff_by_exception,
        retry_if_exception,
        retry_if_result,
        on_exception_callback,
        on_giveup_callback,
    )

    if func is _MISSING:
        return cast(
            "Callable[_P, _T]",
            partial(
                retry,
                tries=tries,
                exceptions=exceptions,
                timeout=timeout,
                default_backoff=default_backoff,
                backoff_by_exception=backoff_by_exception,
                retry_if_exception=retry_if_exception,
                retry_if_result=retry_if_result,
                on_exception_callback=on_exception_callback,
                on_giveup_callback=on_giveup_callback,
            ),
        )

    typed_func: Callable[_P, _T] = cast("Callable[_P, _T]", func)
    is_async_func = inspect.iscoroutinefunction(typed_func)
    is_async_callback = on_exception_callback is not _MISSING and inspect.iscoroutinefunction(on_exception_callback)
    is_async_giveup = on_giveup_callback is not _MISSING and inspect.iscoroutinefunction(on_giveup_callback)

    if not is_async_func and is_async_callback:
        msg = "async on_exception_callback cannot be used with a sync function"
        raise TypeError(msg)
    if not is_async_func and is_async_giveup:
        msg = "async on_giveup_callback cannot be used with a sync function"
        raise TypeError(msg)

    @wraps(typed_func)
    def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:  # type: ignore[return]
        deadline = _compute_deadline(timeout)

        for attempt in range(1, tries + 1):  # pragma: no branch
            try:
                result: _T = typed_func(*args, **kwargs)
                if (
                    retry_if_result is _MISSING
                    or not cast("RetryIfResult", retry_if_result)(result)
                    or attempt >= tries
                    or _is_timed_out(deadline)
                ):
                    return result
                time.sleep(default_backoff(attempt))
            except exceptions as exc:
                if _should_give_up(attempt, tries, deadline, retry_if_exception, exc):
                    if on_giveup_callback is not _MISSING:
                        cast("SyncExceptionCallback", on_giveup_callback)(exc, attempt)
                    raise
                if on_exception_callback is not _MISSING:
                    cast("SyncExceptionCallback", on_exception_callback)(exc, attempt)
                time.sleep(_get_backoff(default_backoff, backoff_by_exception, exc)(attempt))

    @wraps(typed_func)
    async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:  # type: ignore[return]
        async_func = cast("Callable[_P, Awaitable[Any]]", typed_func)
        deadline = _compute_deadline(timeout)

        for attempt in range(1, tries + 1):  # pragma: no branch
            try:
                result: _T = cast("_T", await async_func(*args, **kwargs))
                if (
                    retry_if_result is _MISSING
                    or not cast("RetryIfResult", retry_if_result)(result)
                    or attempt >= tries
                    or _is_timed_out(deadline)
                ):
                    return result
                await asyncio.sleep(default_backoff(attempt))
            except exceptions as exc:
                if _should_give_up(attempt, tries, deadline, retry_if_exception, exc):
                    if on_giveup_callback is not _MISSING:
                        if is_async_giveup:
                            await cast("AsyncExceptionCallback", on_giveup_callback)(exc, attempt)
                        else:
                            cast("SyncExceptionCallback", on_giveup_callback)(exc, attempt)
                    raise
                if on_exception_callback is not _MISSING:
                    if is_async_callback:
                        await cast("AsyncExceptionCallback", on_exception_callback)(exc, attempt)
                    else:
                        cast("SyncExceptionCallback", on_exception_callback)(exc, attempt)
                await asyncio.sleep(_get_backoff(default_backoff, backoff_by_exception, exc)(attempt))

    return async_wrapper if is_async_func else sync_wrapper
