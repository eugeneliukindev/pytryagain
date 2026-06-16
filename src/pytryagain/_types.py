from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeAlias

from pytryagain.backoff import BackOff

Attempt: TypeAlias = int
SyncExceptionCallback: TypeAlias = Callable[[BaseException, Attempt], None]
AsyncExceptionCallback: TypeAlias = Callable[[BaseException, Attempt], Awaitable[None]]
AnyExceptionCallback: TypeAlias = SyncExceptionCallback | AsyncExceptionCallback
RetryIfException: TypeAlias = Callable[[BaseException], bool]
RetryIfResult: TypeAlias = Callable[[Any], bool]  # Any: result type is caller-determined generic
BackOffByException: TypeAlias = Mapping[type[BaseException], BackOff]
