import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from functools import partial, wraps
from typing import Any, ParamSpec, TypeVar, cast, overload

from pytryagain._sentinel import _MISSING, _Sentinel
from pytryagain._types import AnyExceptionCallback, AsyncExceptionCallback, RetryPredicate, SyncExceptionCallback
from pytryagain._utils import _compute_deadline, _should_give_up
from pytryagain.backoff import BackOff, ExponentialJitterBackoff

_P = ParamSpec("_P")
_T = TypeVar("_T")

_DEFAULT_BACKOFF: BackOff = ExponentialJitterBackoff()


def _validate_retry_params(
    tries: int,
    timeout: float | _Sentinel,
    exceptions: tuple[type[BaseException], ...],
) -> None:
    if not isinstance(tries, int) or tries < 1:
        msg = f"tries must be an integer >= 1, got {tries!r}"
        raise ValueError(msg)
    if not isinstance(timeout, _Sentinel) and (not isinstance(timeout, (int, float)) or timeout <= 0):
        msg = f"timeout must be a positive number, got {timeout!r}"
        raise ValueError(msg)
    if not isinstance(exceptions, tuple) or not exceptions:
        msg = f"exceptions must be a non-empty tuple of exception types, got {exceptions!r}"
        raise ValueError(msg)
    if not all(isinstance(exc, type) and issubclass(exc, BaseException) for exc in exceptions):
        msg = f"all items in exceptions must be BaseException subclasses, got {exceptions!r}"
        raise ValueError(msg)


@overload
def retry(
    func: Callable[_P, Awaitable[_T]],
    tries: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float | _Sentinel,
    backoff: BackOff,
    retry_if: RetryPredicate | _Sentinel,
    on_exception_callback: AnyExceptionCallback | _Sentinel,
    on_giveup_callback: AnyExceptionCallback | _Sentinel,
) -> Callable[_P, Awaitable[_T]]: ...


@overload
def retry(
    func: _Sentinel,
    tries: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float | _Sentinel,
    backoff: BackOff,
    retry_if: RetryPredicate | _Sentinel,
    on_exception_callback: AnyExceptionCallback | _Sentinel,
    on_giveup_callback: AnyExceptionCallback | _Sentinel,
) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]: ...


@overload
def retry(
    func: Callable[_P, _T],
    tries: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float | _Sentinel,
    backoff: BackOff,
    retry_if: RetryPredicate | _Sentinel,
    on_exception_callback: SyncExceptionCallback | _Sentinel,
    on_giveup_callback: SyncExceptionCallback | _Sentinel,
) -> Callable[_P, _T]: ...


def retry(
    func: Callable[_P, _T] | _Sentinel = _MISSING,
    tries: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    timeout: float | _Sentinel = _MISSING,
    backoff: BackOff = _DEFAULT_BACKOFF,
    retry_if: RetryPredicate | _Sentinel = _MISSING,
    on_exception_callback: AnyExceptionCallback | _Sentinel = _MISSING,
    on_giveup_callback: AnyExceptionCallback | _Sentinel = _MISSING,
) -> Callable[_P, _T] | Callable[_P, Awaitable[_T]]:
    """Decorator that retries a function on exception.

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
        backoff: Delay strategy between attempts. Receives the current attempt
            number (1-based) and returns the sleep duration in seconds.
        retry_if: Predicate called with the caught exception. Return ``True``
            to retry, ``False`` to re-raise immediately (after calling
            ``on_giveup_callback``). When omitted, all matching exceptions retry.
        on_exception_callback: Called after each failed attempt except the last.
            Receives the exception and the 1-based attempt number. For async
            functions, both sync and async callbacks are accepted. For sync
            functions, only a sync callback is allowed.
        on_giveup_callback: Called once when all attempts are exhausted or a
            retry is aborted by ``retry_if``, before re-raising the exception.
            Same sync/async rules as ``on_exception_callback``.

    Returns:
        The wrapped function preserving the original signature, or a partially
        applied decorator when ``func`` is not provided.

    Raises:
        ValueError: If an async callback is passed for a sync function.
        BaseException: The original exception after all attempts are exhausted,
            timeout is exceeded, or ``retry_if`` returns ``False``.

    Examples:
        Simplest usage — 3 attempts with 1 s constant delay:

        >>> @retry
        ... def fetch_data(url: str) -> bytes: ...

        Async function with exponential backoff and total timeout:

        >>> @retry(tries=5, backoff=ExponentialBackoff(), timeout=30.0)
        ... async def send_message(text: str) -> None: ...

        Retry only on specific exception types:

        >>> @retry(tries=4, exceptions=(TimeoutError, ConnectionError))
        ... def connect(host: str) -> None: ...

        Log every failed attempt:

        >>> def log_attempt(exc: BaseException, attempt: int) -> None:
        ...     print(f"attempt {attempt} failed: {exc}")
        ...
        >>> @retry(tries=3, on_exception_callback=log_attempt)
        ... def unstable_call() -> None: ...

        Retry only when the error is transient (e.g. HTTP 503):

        >>> @retry(tries=5, retry_if=lambda e: getattr(e, "status_code", None) == 503)
        ... def call_api() -> dict: ...  # type: ignore[empty-body]

        Alert when all retries are exhausted:

        >>> def alert(exc: BaseException, attempt: int) -> None:
        ...     print(f"gave up after {attempt} attempts: {exc}")
        ...
        >>> @retry(tries=3, on_giveup_callback=alert)
        ... def critical_job() -> None: ...

        Async giveup callback:

        >>> async def async_alert(exc: BaseException, attempt: int) -> None:
        ...     await notify_slack(f"job failed: {exc}")
        ...
        >>> @retry(tries=3, on_giveup_callback=async_alert)
        ... async def critical_async_job() -> None: ...
    """
    _validate_retry_params(tries, timeout, exceptions)

    if isinstance(func, _Sentinel):
        return cast(
            "Callable[_P, _T]",
            partial(
                retry,
                tries=tries,
                exceptions=exceptions,
                timeout=timeout,
                backoff=backoff,
                retry_if=retry_if,
                on_exception_callback=on_exception_callback,
                on_giveup_callback=on_giveup_callback,
            ),
        )

    is_async_func = inspect.iscoroutinefunction(func)
    is_async_callback = not isinstance(on_exception_callback, _Sentinel) and inspect.iscoroutinefunction(
        on_exception_callback
    )
    is_async_giveup = not isinstance(on_giveup_callback, _Sentinel) and inspect.iscoroutinefunction(on_giveup_callback)

    if not is_async_func and is_async_callback:
        msg = "async on_exception_callback cannot be used with sync func"
        raise ValueError(msg)
    if not is_async_func and is_async_giveup:
        msg = "async on_giveup_callback cannot be used with sync func"
        raise ValueError(msg)

    @wraps(func)
    def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:  # type: ignore[return]
        deadline = _compute_deadline(timeout)

        for attempt in range(1, tries + 1):  # pragma: no branch
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if _should_give_up(attempt, tries, deadline, retry_if, e):
                    if not isinstance(on_giveup_callback, _Sentinel):
                        cast("SyncExceptionCallback", on_giveup_callback)(e, attempt)
                    raise

                if not isinstance(on_exception_callback, _Sentinel):
                    cast("SyncExceptionCallback", on_exception_callback)(e, attempt)
                time.sleep(backoff(attempt))

    @wraps(func)
    async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:  # type: ignore[return]
        async_func = cast("Callable[_P, Awaitable[Any]]", func)
        deadline = _compute_deadline(timeout)

        for attempt in range(1, tries + 1):  # pragma: no branch
            try:
                return cast("_T", await async_func(*args, **kwargs))
            except exceptions as e:
                if _should_give_up(attempt, tries, deadline, retry_if, e):
                    if not isinstance(on_giveup_callback, _Sentinel):
                        if is_async_giveup:
                            await cast("AsyncExceptionCallback", on_giveup_callback)(e, attempt)
                        else:
                            cast("SyncExceptionCallback", on_giveup_callback)(e, attempt)
                    raise

                if not isinstance(on_exception_callback, _Sentinel):
                    if is_async_callback:
                        await cast("AsyncExceptionCallback", on_exception_callback)(e, attempt)
                    else:
                        cast("SyncExceptionCallback", on_exception_callback)(e, attempt)
                await asyncio.sleep(backoff(attempt))

    return async_wrapper if is_async_func else sync_wrapper
