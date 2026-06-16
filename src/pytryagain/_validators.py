from collections.abc import Mapping

from ._types import AnyExceptionCallback, BackOffByException, ShouldRetry
from .backoff import BackOff


def _validate_max_attempts(max_attempts: object) -> None:
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
        msg = f"max_attempts must be int, got {type(max_attempts).__name__!r}"
        raise TypeError(msg)
    if max_attempts < 1:
        msg = f"max_attempts must be >= 1, got {max_attempts!r}"
        raise ValueError(msg)


def _validate_exceptions(exceptions: object) -> None:
    if not isinstance(exceptions, tuple):
        msg = f"exceptions must be a tuple, got {type(exceptions).__name__!r}"
        raise TypeError(msg)
    if not exceptions:
        msg = "exceptions must be a non-empty tuple of BaseException subclasses"
        raise ValueError(msg)
    if not all(isinstance(exc, type) and issubclass(exc, BaseException) for exc in exceptions):
        msg = f"all items in exceptions must be BaseException subclasses, got {exceptions!r}"
        raise TypeError(msg)


def _validate_timeout(timeout: object) -> None:
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        msg = f"timeout must be a positive number, got {type(timeout).__name__!r}"
        raise TypeError(msg)
    if timeout <= 0:
        msg = f"timeout must be > 0, got {timeout!r}"
        raise ValueError(msg)


def _validate_default_backoff(default_backoff: object) -> None:
    if not isinstance(default_backoff, BackOff):
        msg = f"default_backoff must implement BackOff protocol, got {type(default_backoff).__name__!r}"
        raise TypeError(msg)


def _validate_backoff_by_exception(backoff_by_exception: object) -> None:
    if backoff_by_exception is None:
        return
    if not isinstance(backoff_by_exception, Mapping):
        msg = f"backoff_by_exception must be a Mapping, got {type(backoff_by_exception).__name__!r}"
        raise TypeError(msg)
    for k, v in backoff_by_exception.items():
        if not (isinstance(k, type) and issubclass(k, BaseException)):
            msg = f"backoff_by_exception keys must be BaseException subclasses, got {k!r}"
            raise TypeError(msg)
        if not isinstance(v, BackOff):
            msg = f"backoff_by_exception values must implement BackOff protocol, got {type(v).__name__!r}"
            raise TypeError(msg)


def _validate_should_retry(should_retry: object) -> None:
    if should_retry is not None and not callable(should_retry):
        msg = f"should_retry must be callable, got {type(should_retry).__name__!r}"
        raise TypeError(msg)


def _validate_on_retry_callback(on_retry_callback: object) -> None:
    if on_retry_callback is not None and not callable(on_retry_callback):
        msg = f"on_retry_callback must be callable, got {type(on_retry_callback).__name__!r}"
        raise TypeError(msg)


def _validate_on_give_up_callback(on_give_up_callback: object) -> None:
    if on_give_up_callback is not None and not callable(on_give_up_callback):
        msg = f"on_give_up_callback must be callable, got {type(on_give_up_callback).__name__!r}"
        raise TypeError(msg)


def _validate_sync_func_callback_compat(
    *,
    is_async_func: bool,
    is_async_retry_callback: bool,
    is_async_give_up_callback: bool,
) -> None:
    if not is_async_func:
        if is_async_retry_callback:
            msg = "async on_retry_callback cannot be used with a sync function"
            raise TypeError(msg)
        if is_async_give_up_callback:
            msg = "async on_give_up_callback cannot be used with a sync function"
            raise TypeError(msg)


def _validate_retry_params(
    max_attempts: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | None,
    should_retry: ShouldRetry | None,
    on_retry_callback: AnyExceptionCallback | None,
    on_give_up_callback: AnyExceptionCallback | None,
) -> None:
    _validate_max_attempts(max_attempts)
    _validate_exceptions(exceptions)
    _validate_timeout(timeout)
    _validate_default_backoff(default_backoff)
    _validate_backoff_by_exception(backoff_by_exception)
    _validate_should_retry(should_retry)
    _validate_on_retry_callback(on_retry_callback)
    _validate_on_give_up_callback(on_give_up_callback)
