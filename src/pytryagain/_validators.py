from collections.abc import Mapping
from typing import cast

from ._sentinel import _MISSING, _Sentinel
from ._types import AnyExceptionCallback, BackOffByException, RetryIfException, RetryIfResult
from .backoff import BackOff


def _validate_tries(tries: object) -> None:
    if not isinstance(tries, int) or isinstance(tries, bool):
        msg = f"tries must be int, got {type(tries).__name__!r}"
        raise TypeError(msg)
    if tries < 1:
        msg = f"tries must be >= 1, got {tries!r}"
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
    if timeout is _MISSING:
        return
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
    if backoff_by_exception is _MISSING:
        return
    if not isinstance(backoff_by_exception, Mapping):
        msg = f"backoff_by_exception must be a Mapping, got {type(backoff_by_exception).__name__!r}"
        raise TypeError(msg)
    for k, v in cast("Mapping[object, object]", backoff_by_exception).items():
        if not (isinstance(k, type) and issubclass(k, BaseException)):
            msg = f"backoff_by_exception keys must be BaseException subclasses, got {k!r}"
            raise TypeError(msg)
        if not isinstance(v, BackOff):
            msg = f"backoff_by_exception values must implement BackOff protocol, got {type(v).__name__!r}"
            raise TypeError(msg)


def _validate_retry_if_exception(retry_if_exception: object) -> None:
    if retry_if_exception is not _MISSING and not callable(retry_if_exception):
        msg = f"retry_if_exception must be callable, got {type(retry_if_exception).__name__!r}"
        raise TypeError(msg)


def _validate_retry_if_result(retry_if_result: object) -> None:
    if retry_if_result is not _MISSING and not callable(retry_if_result):
        msg = f"retry_if_result must be callable, got {type(retry_if_result).__name__!r}"
        raise TypeError(msg)


def _validate_on_exception_callback(on_exception_callback: object) -> None:
    if on_exception_callback is not _MISSING and not callable(on_exception_callback):
        msg = f"on_exception_callback must be callable, got {type(on_exception_callback).__name__!r}"
        raise TypeError(msg)


def _validate_on_giveup_callback(on_giveup_callback: object) -> None:
    if on_giveup_callback is not _MISSING and not callable(on_giveup_callback):
        msg = f"on_giveup_callback must be callable, got {type(on_giveup_callback).__name__!r}"
        raise TypeError(msg)


def _validate_retry_params(
    tries: int,
    exceptions: tuple[type[BaseException], ...],
    timeout: float | _Sentinel,
    default_backoff: BackOff,
    backoff_by_exception: BackOffByException | _Sentinel,
    retry_if_exception: RetryIfException | _Sentinel,
    retry_if_result: RetryIfResult | _Sentinel,
    on_exception_callback: AnyExceptionCallback | _Sentinel,
    on_giveup_callback: AnyExceptionCallback | _Sentinel,
) -> None:
    _validate_tries(tries)
    _validate_exceptions(exceptions)
    _validate_timeout(timeout)
    _validate_default_backoff(default_backoff)
    _validate_backoff_by_exception(backoff_by_exception)
    _validate_retry_if_exception(retry_if_exception)
    _validate_retry_if_result(retry_if_result)
    _validate_on_exception_callback(on_exception_callback)
    _validate_on_giveup_callback(on_giveup_callback)
