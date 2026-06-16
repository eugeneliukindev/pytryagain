import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from functools import partial, wraps
from typing import ParamSpec, TypeVar, overload

from ._types import (
    AnyExceptionCallback,
    BackOffByException,
    ShouldRetry,
    SyncExceptionCallback,
)
from ._utils import (
    _always_retry,
    _compute_deadline,
    _get_backoff,
    _invoke_callback,
    _noop_exception_callback,
    _should_give_up,
)
from ._validators import _validate_retry_params, _validate_sync_func_callback_compat
from .backoff import BackOff, ExponentialJitterBackoff

_P = ParamSpec("_P")
_T = TypeVar("_T")

_DEFAULT_BACKOFF: BackOff = ExponentialJitterBackoff()


@overload
def retry(
    func: Callable[_P, Awaitable[_T]],
    max_attempts: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | None,
    should_retry: ShouldRetry | None,
    on_retry_callback: AnyExceptionCallback | None,
    on_give_up_callback: AnyExceptionCallback | None,
) -> Callable[_P, Awaitable[_T]]: ...


@overload
def retry(
    func: None,
    max_attempts: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | None,
    should_retry: ShouldRetry | None,
    on_retry_callback: AnyExceptionCallback | None,
    on_give_up_callback: AnyExceptionCallback | None,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]: ...


@overload
def retry(
    func: Callable[_P, _T],
    max_attempts: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | None,
    should_retry: ShouldRetry | None,
    on_retry_callback: SyncExceptionCallback | None,
    on_give_up_callback: SyncExceptionCallback | None,
) -> Callable[_P, _T]: ...


def retry(
    func: Callable[_P, _T] | None = None,
    max_attempts: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    timeout: float = float("inf"),
    default_backoff: BackOff = _DEFAULT_BACKOFF,
    backoff_by_exception: BackOffByException | None = None,
    should_retry: ShouldRetry | None = None,
    on_retry_callback: AnyExceptionCallback | None = None,
    on_give_up_callback: AnyExceptionCallback | None = None,
) -> Callable[_P, _T] | Callable[_P, Awaitable[_T]]:
    """Decorator that retries a function on exception.

    Supports both sync and async functions. Can be used as a plain decorator
    ``@retry`` or as a decorator factory ``@retry(max_attempts=5)``.

    Args:
        func: The function to wrap. When omitted, returns a partially applied
            decorator (decorator factory mode).
        max_attempts: Total number of attempts, including the first call.
            ``max_attempts=1`` means no retries. Must be >= 1.
        exceptions: Tuple of exception types that trigger a retry. Any other
            exception propagates immediately without retrying.
        timeout: Total time budget in seconds across all attempts. Once elapsed,
            the current exception is re-raised without further retries.
        default_backoff: Delay strategy between attempts. Receives the current attempt
            number (1-based) and returns the sleep duration in seconds.
        backoff_by_exception: Per-exception-type delay overrides. Keys are
            BaseException subclasses; the first matching key wins. Falls back to
            ``default_backoff`` when no key matches.
        should_retry: Predicate called with the caught exception. Return ``True``
            to retry, ``False`` to re-raise immediately (after calling
            ``on_give_up_callback``). When omitted, all matching exceptions retry.
        on_retry_callback: Called after each failed attempt except the last.
            Receives the exception and the 1-based attempt number. For async
            functions, both sync and async callbacks are accepted. For sync
            functions, only a sync callback is allowed.
        on_give_up_callback: Called once when all attempts are exhausted or a
            retry is aborted by ``should_retry``, before re-raising the exception.
            Same sync/async rules as ``on_retry_callback``.

    Returns:
        The wrapped function preserving the original signature, or a partially
        applied decorator when ``func`` is not provided.

    Raises:
        TypeError: If any parameter has an incorrect type, or if an async callback
            is passed for a sync function.
        ValueError: If ``max_attempts`` < 1, ``timeout`` <= 0, or ``exceptions`` is empty.
        BaseException: The original exception after all attempts are exhausted,
            timeout is exceeded, or ``should_retry`` returns ``False``.

    See also: https://github.com/eugeneliukindev/pytryagain/blob/main/README.md#examples
    """
    _validate_retry_params(
        max_attempts,
        exceptions,
        timeout,
        default_backoff,
        backoff_by_exception,
        should_retry,
        on_retry_callback,
        on_give_up_callback,
    )

    should_retry = _always_retry if should_retry is None else should_retry
    on_retry_callback = _noop_exception_callback if on_retry_callback is None else on_retry_callback
    on_give_up_callback = _noop_exception_callback if on_give_up_callback is None else on_give_up_callback
    backoff_by_exception = {} if backoff_by_exception is None else backoff_by_exception

    if func is None:
        return partial(  # type: ignore[return-value]
            retry,
            max_attempts=max_attempts,
            exceptions=exceptions,
            timeout=timeout,
            default_backoff=default_backoff,
            backoff_by_exception=backoff_by_exception,
            should_retry=should_retry,
            on_retry_callback=on_retry_callback,
            on_give_up_callback=on_give_up_callback,
        )

    is_async_func = inspect.iscoroutinefunction(func)
    is_async_retry_callback = inspect.iscoroutinefunction(on_retry_callback)
    is_async_give_up_callback = inspect.iscoroutinefunction(on_give_up_callback)

    _validate_sync_func_callback_compat(
        is_async_func=is_async_func,
        is_async_retry_callback=is_async_retry_callback,
        is_async_give_up_callback=is_async_give_up_callback,
    )

    @wraps(func)
    def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:  # type: ignore[return]
        deadline = _compute_deadline(timeout)

        for attempt in range(1, max_attempts + 1):  # pragma: no branch
            try:
                return func(*args, **kwargs)
            except exceptions as exception:
                if _should_give_up(attempt, max_attempts, deadline, should_retry, exception):
                    on_give_up_callback(exception, attempt)
                    raise
                on_retry_callback(exception, attempt)
                backoff = _get_backoff(default_backoff, backoff_by_exception, exception)
                time.sleep(backoff(attempt))

    @wraps(func)
    async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:  # type: ignore[return]
        deadline = _compute_deadline(timeout)

        for attempt in range(1, max_attempts + 1):  # pragma: no branch
            try:
                return await func(*args, **kwargs)  # type: ignore[misc,no-any-return]
            except exceptions as exception:
                if _should_give_up(attempt, max_attempts, deadline, should_retry, exception):
                    await _invoke_callback(on_give_up_callback, exception, attempt, is_async=is_async_give_up_callback)
                    raise
                await _invoke_callback(on_retry_callback, exception, attempt, is_async=is_async_retry_callback)
                backoff = _get_backoff(default_backoff, backoff_by_exception, exception)
                await asyncio.sleep(backoff(attempt))

    return async_wrapper if is_async_func else sync_wrapper
