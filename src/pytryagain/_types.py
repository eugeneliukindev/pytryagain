from collections.abc import Awaitable, Callable
from typing import TypeAlias

Attempt: TypeAlias = int
SyncExceptionCallback: TypeAlias = Callable[[BaseException, Attempt], None]
AsyncExceptionCallback: TypeAlias = Callable[[BaseException, Attempt], Awaitable[None]]
AnyExceptionCallback: TypeAlias = SyncExceptionCallback | AsyncExceptionCallback
RetryPredicate: TypeAlias = Callable[[BaseException], bool]
