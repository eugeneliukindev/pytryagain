from collections.abc import Awaitable, Callable, Mapping
from typing import TypeAlias

from pytryagain.backoff import BackOff

Attempt: TypeAlias = int
SyncExceptionCallback: TypeAlias = Callable[[BaseException, Attempt], None]
AsyncExceptionCallback: TypeAlias = Callable[[BaseException, Attempt], Awaitable[None]]
AnyExceptionCallback: TypeAlias = SyncExceptionCallback | AsyncExceptionCallback
ShouldRetry: TypeAlias = Callable[[BaseException], bool]
BackOffByException: TypeAlias = Mapping[type[BaseException], BackOff]
