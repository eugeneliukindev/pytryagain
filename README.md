# pytryagain

**A lightweight, zero-dependency retry decorator for sync and async Python functions.**

[![CI](https://github.com/eugeneliukindev/pytryagain/actions/workflows/ci.yml/badge.svg)](https://github.com/eugeneliukindev/pytryagain/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/eugeneliukindev/pytryagain/branch/main/graph/badge.svg)](https://codecov.io/gh/eugeneliukindev/pytryagain)
[![PyPI](https://img.shields.io/pypi/v/pytryagain)](https://pypi.org/project/pytryagain/)
[![Python](https://img.shields.io/badge/python-3.10_%7C_3.11_%7C_3.12_%7C_3.13_%7C_3.14_%7C_3.15-blue)](https://pypi.org/project/pytryagain/)
[![License](https://img.shields.io/github/license/eugeneliukindev/pytryagain)](LICENSE)

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Examples](#examples)
  - [Basic usage](#basic-usage)
  - [Async functions](#async-functions)
  - [Decorator factory](#decorator-factory)
  - [Limit retried exceptions](#limit-retried-exceptions)
  - [Backoff strategies](#backoff-strategies)
  - [Per-exception backoff](#per-exception-backoff)
  - [Timeout](#timeout)
  - [Conditional retry](#conditional-retry)
  - [Callbacks](#callbacks)
  - [Async callbacks](#async-callbacks)
- [API Reference](#api-reference)
- [Backoff Strategies](#backoff-strategies-1)
- [License](#license)

---

## Installation

```bash
pip install pytryagain
```

---

## Quick Start

```python
from pytryagain import retry

@retry
def fetch_data(url: str) -> bytes:
    ...  # retried up to 3 times on any Exception
```

---

## Examples

### Basic usage

Use `@retry` as a plain decorator — **3 attempts** with exponential jitter backoff by default:

```python
from pytryagain import retry

@retry
def connect_to_db() -> Connection:
    return db.connect()
```

Customise the number of attempts with `max_attempts`:

```python
@retry(max_attempts=5)
def connect_to_db() -> Connection:
    return db.connect()
```

Use `max_attempts=1` to disable retries entirely while keeping the same call signature
(useful for toggling retries via configuration):

```python
@retry(max_attempts=1)
def call_once() -> dict:
    ...  # raises immediately on the first failure, never retries
```

---

### Async functions

Works identically with `async def` — uses `asyncio.sleep` between attempts instead of `time.sleep`:

```python
@retry(max_attempts=5)
async def fetch_user(user_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}")
        response.raise_for_status()
        return response.json()
```

Combine it with `timeout` and `exceptions` to bound both the attempt count and the wall-clock
budget for a single call:

```python
@retry(max_attempts=5, timeout=10.0, exceptions=(ConnectionError, TimeoutError))
async def fetch_user(user_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}")
        response.raise_for_status()
        return response.json()
```

---

### Decorator factory

Apply a shared retry policy across multiple functions:

```python
from pytryagain import retry
from pytryagain.backoff import ConstantBackoff

http_retry = retry(max_attempts=4, default_backoff=ConstantBackoff(delay=1.0))


@http_retry
def get_orders() -> list:
  ...


@http_retry
def get_inventory() -> list:
  ...
```

> [!WARNING]
> Don't share a single `DecorrelatedJitterBackoff` instance across a `retry()` factory used by
> multiple functions. It carries mutable state (`prev_sleep`) between calls, so concurrent or
> interleaved calls to the decorated functions will read and mutate the same state. Create a
> separate instance per function, or use a stateless strategy instead.

---

### Limit retried exceptions

By default all `Exception` subclasses trigger a retry. Use `exceptions` to narrow this:

```python
@retry(max_attempts=4, exceptions=(TimeoutError, ConnectionError))
def connect(host: str) -> None:
    ...  # ValueError and others propagate immediately without retrying
```

> [!NOTE]
> Exceptions that don't match `exceptions` propagate immediately — they never reach
> `should_retry` or `on_retry_callback`/`on_give_up_callback`.

---

### Backoff strategies

Control the delay between attempts with any backoff strategy:

```python
from pytryagain.backoff import (
    ConstantBackoff,
    LinearBackoff,
    ExponentialBackoff,
    ExponentialJitterBackoff,
)

# Wait 2 s between every attempt
@retry(max_attempts=5, default_backoff=ConstantBackoff(delay=2.0))
def fetch() -> None: ...

# Wait 1 s, 2 s, 3 s, …
@retry(max_attempts=5, default_backoff=LinearBackoff(base=1.0))
def fetch() -> None: ...

# Wait 2 s, 4 s, 8 s, … (doubles each time)
@retry(max_attempts=5, default_backoff=ExponentialBackoff(base=2.0, initial=1.0))
def fetch() -> None: ...

# Exponential with random jitter — avoids thundering herd
@retry(max_attempts=5, default_backoff=ExponentialJitterBackoff(base=2.0, initial=1.0))
def fetch() -> None: ...
```

---

### Per-exception backoff

Override the delay for specific exception types with `backoff_by_exception`:

```python
from pytryagain.backoff import ConstantBackoff, ExponentialJitterBackoff

@retry(
    max_attempts=5,
    default_backoff=ExponentialJitterBackoff(),
    backoff_by_exception={
        RateLimitError: ConstantBackoff(delay=30.0),
        ConnectionError: ConstantBackoff(delay=1.0),
    },
)
def call_api() -> dict:
    ...
```

> [!NOTE]
> Matching uses `isinstance`, and the **first matching key wins**, in dict insertion order.
> If one exception type is a subclass of another key in the mapping, list the more specific
> subclass first. Exceptions that don't match any key fall back to `default_backoff`.

When one exception type subclasses another in the mapping, put the subclass first so it gets
its own delay instead of matching the parent's entry:

```python
class TransientError(Exception): ...
class RateLimitError(TransientError): ...

@retry(
    max_attempts=4,
    exceptions=(TransientError,),
    backoff_by_exception={
        RateLimitError: ConstantBackoff(delay=10.0),   # checked first
        TransientError: ConstantBackoff(delay=1.0),    # catches everything else
    },
)
def call_api() -> dict:
    ...
```

---

### Timeout

Stop retrying once a total wall-clock budget is exhausted, regardless of `max_attempts`:

```python
@retry(max_attempts=10, timeout=30.0)
def call_api() -> dict:
    ...  # gives up after 30 seconds even if not all attempts are used
```

`timeout` and `max_attempts` work together — whichever limit is hit first wins.

> [!NOTE]
> The timeout budget starts fresh on every call to the decorated function — it is not shared
> or accumulated across separate calls.

---

### Conditional retry

Use `should_retry` to inspect the exception and decide whether to retry:

```python
# Retry only on HTTP 503 Service Unavailable
@retry(max_attempts=5, should_retry=lambda exc: getattr(exc, "status_code", None) == 503)
def call_api() -> dict:
    ...

# Retry only on transient database errors
@retry(max_attempts=3, should_retry=lambda exc: isinstance(exc, OperationalError) and exc.is_transient)
def query_db() -> list:
    ...
```

> [!IMPORTANT]
> Returning `False` from `should_retry` immediately re-raises the exception, after calling
> `on_give_up_callback` if one is set — `on_retry_callback` is **not** called in this case.

---

### Callbacks

Run a function after each failed attempt, or once when all retries are exhausted:

```python
import logging

logger = logging.getLogger(__name__)

def log_attempt(exc: BaseException, attempt: int) -> None:
    logger.warning("attempt %d failed: %s", attempt, exc)

def alert_on_give_up(exc: BaseException, attempt: int) -> None:
    logger.error("gave up after %d attempts: %s", attempt, exc)

@retry(
    max_attempts=4,
    on_retry_callback=log_attempt,
    on_give_up_callback=alert_on_give_up,
)
def send_payment(amount: float) -> None:
    ...
```

Both callbacks receive `(exc, attempt)` where `attempt` is 1-based.

> [!NOTE]
> `on_retry_callback` runs after every failed attempt except the last — it is skipped on the
> attempt that triggers `on_give_up_callback`.

---

### Async callbacks

Async functions accept both sync and async callbacks:

```python
async def notify_slack(exc: BaseException, attempt: int) -> None:
    await slack.post(f"Retry #{attempt} failed: {exc}")

async def page_oncall(exc: BaseException, attempt: int) -> None:
    await pagerduty.trigger(f"All retries exhausted: {exc}")

@retry(
    max_attempts=5,
    on_retry_callback=notify_slack,
    on_give_up_callback=page_oncall,
)
async def process_job(job_id: str) -> None:
    ...
```

> [!WARNING]
> Async callbacks cannot be used with sync functions — a `TypeError` is raised at decoration
> time, before the function is ever called.

---

## API Reference

### `retry`

```python
retry(
    func=...,
    max_attempts=3,
    exceptions=(Exception,),
    timeout=...,
    default_backoff=ExponentialJitterBackoff(),
    backoff_by_exception=...,
    should_retry=...,
    on_retry_callback=...,
    on_give_up_callback=...,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `func` | `Callable` | — | Function to wrap. Omit to use as a decorator factory. |
| `max_attempts` | `int` | `3` | Total attempts including the first call. `max_attempts=1` means no retries. |
| `exceptions` | `tuple[type[BaseException], ...]` | `(Exception,)` | Exception types that trigger a retry. |
| `timeout` | `float` | — | Total time budget in seconds across all attempts. |
| `default_backoff` | `BackOff` | `ExponentialJitterBackoff()` | Delay strategy between attempts. |
| `backoff_by_exception` | `Mapping[type[BaseException], BackOff]` | — | Per-exception-type delay overrides. |
| `should_retry` | `Callable[[BaseException], bool]` | — | Predicate to decide whether to retry. `False` re-raises immediately. |
| `on_retry_callback` | `Callable[[BaseException, int], None]` | — | Called after each failed attempt except the last. |
| `on_give_up_callback` | `Callable[[BaseException, int], None]` | — | Called once when all attempts are exhausted. |

> [!NOTE]
> All parameters except `func` are keyword-only in practice — pass them by name, as shown in
> every example above.

---

## Backoff Strategies

| Strategy | Description | Parameters |
|---|---|---|
| `ConstantBackoff` | Fixed delay every attempt | `delay=1.0` |
| `LinearBackoff` | Grows linearly: `base * attempt` | `base=1.0` |
| `ExponentialBackoff` | Doubles each attempt: `initial * base ** attempt` | `base=2.0`, `initial=1.0` |
| `ExponentialJitterBackoff` | Exponential with random jitter in `[0, exp]` | `base=2.0`, `initial=1.0` |
| `FullJitterBackoff` | Random in `[0, min(cap, base ** attempt)]` | `cap=60.0`, `base=2.0` |
| `EqualJitterBackoff` | Half fixed, half random | `cap=60.0`, `base=2.0` |
| `DecorrelatedJitterBackoff` | Each delay based on previous sleep | `base=1.0`, `cap=60.0` |
| `FibonacciBackoff` | Fibonacci sequence scaled by `base` | `base=1.0` |
| `TruncatedExponentialBackoff` | Exponential capped at a maximum | `base=2.0`, `initial=1.0`, `cap=60.0` |

> [!WARNING]
> `DecorrelatedJitterBackoff` is the only stateful strategy — it mutates `prev_sleep` on every
> call. Give each decorated function (or each `retry()` factory) its own instance; never share
> one across multiple functions or call sites.

All strategies implement the `BackOff` protocol — you can supply your own. A plain function
works:

```python
def my_backoff(attempt: int) -> float:
    return min(attempt * 0.5, 10.0)

@retry(max_attempts=5, default_backoff=my_backoff)
def fetch() -> None: ...
```

So does a `lambda`:

```python
@retry(max_attempts=5, default_backoff=lambda attempt: attempt * 0.2)
def fetch() -> None: ...
```

Or a small `dataclass` if the strategy needs its own parameters:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class CappedLinearBackoff:
    step: float = 1.0
    cap: float = 10.0

    def __call__(self, attempt: int) -> float:
        return min(self.step * attempt, self.cap)

@retry(max_attempts=5, default_backoff=CappedLinearBackoff(step=2.0, cap=8.0))
def fetch() -> None: ...
```

> [!TIP]
> Any callable matching `(attempt: int) -> float` satisfies the `BackOff` protocol — a plain
> function, a lambda, or a `dataclass` with `__call__` all work, no inheritance required.

---

## License

MIT — see [LICENSE](LICENSE).
