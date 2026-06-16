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

Customise the number of attempts with `tries`:

```python
@retry(tries=5)
def connect_to_db() -> Connection:
    return db.connect()
```

---

### Async functions

Works identically with `async def` — uses `asyncio.sleep` between attempts instead of `time.sleep`:

```python
@retry(tries=5)
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

http_retry = retry(tries=4, backoff=ConstantBackoff(delay=1.0))

@http_retry
def get_orders() -> list:
    ...

@http_retry
def get_inventory() -> list:
    ...
```

---

### Limit retried exceptions

By default all `Exception` subclasses trigger a retry. Use `exceptions` to narrow this:

```python
@retry(tries=4, exceptions=(TimeoutError, ConnectionError))
def connect(host: str) -> None:
    ...  # ValueError and others propagate immediately without retrying
```

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
@retry(tries=5, backoff=ConstantBackoff(delay=2.0))
def fetch() -> None: ...

# Wait 1 s, 2 s, 3 s, …
@retry(tries=5, backoff=LinearBackoff(base=1.0))
def fetch() -> None: ...

# Wait 2 s, 4 s, 8 s, … (doubles each time)
@retry(tries=5, backoff=ExponentialBackoff(base=2.0, initial=1.0))
def fetch() -> None: ...

# Exponential with random jitter — avoids thundering herd
@retry(tries=5, backoff=ExponentialJitterBackoff(base=2.0, initial=1.0))
def fetch() -> None: ...
```

---

### Timeout

Stop retrying once a total wall-clock budget is exhausted, regardless of `tries`:

```python
@retry(tries=10, timeout=30.0)
def call_api() -> dict:
    ...  # gives up after 30 seconds even if not all tries are used
```

`timeout` and `tries` work together — whichever limit is hit first wins.

---

### Conditional retry

Use `retry_if` to inspect the exception and decide whether to retry:

```python
# Retry only on HTTP 503 Service Unavailable
@retry(tries=5, retry_if=lambda exc: getattr(exc, "status_code", None) == 503)
def call_api() -> dict:
    ...

# Retry only on transient database errors
@retry(tries=3, retry_if=lambda exc: isinstance(exc, OperationalError) and exc.is_transient)
def query_db() -> list:
    ...
```

Returning `False` from `retry_if` immediately re-raises the exception (after calling `on_giveup_callback` if set).

---

### Callbacks

Run a function after each failed attempt, or once when all retries are exhausted:

```python
import logging

logger = logging.getLogger(__name__)

def log_attempt(exc: BaseException, attempt: int) -> None:
    logger.warning("attempt %d failed: %s", attempt, exc)

def alert_on_giveup(exc: BaseException, attempt: int) -> None:
    logger.error("gave up after %d attempts: %s", attempt, exc)

@retry(
    tries=4,
    on_exception_callback=log_attempt,
    on_giveup_callback=alert_on_giveup,
)
def send_payment(amount: float) -> None:
    ...
```

Both callbacks receive `(exc, attempt)` where `attempt` is 1-based.

---

### Async callbacks

Async functions accept both sync and async callbacks:

```python
async def notify_slack(exc: BaseException, attempt: int) -> None:
    await slack.post(f"Retry #{attempt} failed: {exc}")

async def page_oncall(exc: BaseException, attempt: int) -> None:
    await pagerduty.trigger(f"All retries exhausted: {exc}")

@retry(
    tries=5,
    on_exception_callback=notify_slack,
    on_giveup_callback=page_oncall,
)
async def process_job(job_id: str) -> None:
    ...
```

> **Note:** async callbacks cannot be used with sync functions — a `ValueError` is raised at decoration time.

---

## API Reference

### `retry`

```python
retry(
    func=...,
    tries=3,
    exceptions=(Exception,),
    timeout=...,
    backoff=ExponentialJitterBackoff(),
    retry_if=...,
    on_exception_callback=...,
    on_giveup_callback=...,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `func` | `Callable` | — | Function to wrap. Omit to use as a decorator factory. |
| `tries` | `int` | `3` | Total attempts including the first call. `tries=1` means no retries. |
| `exceptions` | `tuple[type[BaseException], ...]` | `(Exception,)` | Exception types that trigger a retry. |
| `timeout` | `float` | — | Total time budget in seconds across all attempts. |
| `backoff` | `BackOff` | `ExponentialJitterBackoff()` | Delay strategy between attempts. |
| `retry_if` | `Callable[[BaseException], bool]` | — | Predicate to decide whether to retry. `False` re-raises immediately. |
| `on_exception_callback` | `Callable[[BaseException, int], None]` | — | Called after each failed attempt except the last. |
| `on_giveup_callback` | `Callable[[BaseException, int], None]` | — | Called once when all attempts are exhausted. |

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

All strategies implement the `BackOff` protocol — you can supply your own:

```python
def my_backoff(attempt: int) -> float:
    return min(attempt * 0.5, 10.0)

@retry(tries=5, backoff=my_backoff)
def fetch() -> None: ...
```

---

## License

MIT — see [LICENSE](LICENSE).
