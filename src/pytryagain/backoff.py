import random
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class BackOff(Protocol):
    def __call__(self, attempt: int) -> float: ...


@dataclass(frozen=True, slots=True)
class ConstantBackoff:
    delay: float = 1.0

    def __call__(self, attempt: int) -> float:
        return self.delay


@dataclass(frozen=True, slots=True)
class LinearBackoff:
    base: float = 1.0

    def __call__(self, attempt: int) -> float:
        return self.base * attempt


@dataclass(frozen=True, slots=True)
class ExponentialBackoff:
    base: float = 2.0
    initial: float = 1.0

    def __call__(self, attempt: int) -> float:
        return self.initial * (self.base**attempt)


@dataclass(frozen=True, slots=True)
class ExponentialJitterBackoff:
    base: float = 2.0
    initial: float = 1.0

    def __call__(self, attempt: int) -> float:
        exp: float = self.initial * (self.base**attempt)
        return random.uniform(0, exp)


@dataclass(frozen=True, slots=True)
class FullJitterBackoff:
    cap: float = 60.0
    base: float = 2.0

    def __call__(self, attempt: int) -> float:
        return random.uniform(0, min(self.cap, self.base**attempt))


@dataclass(frozen=True, slots=True)
class EqualJitterBackoff:
    cap: float = 60.0
    base: float = 2.0

    def __call__(self, attempt: int) -> float:
        v: float = min(self.cap, self.base**attempt) / 2
        return v + random.uniform(0, v)


@dataclass
class DecorrelatedJitterBackoff:
    base: float = 1.0
    cap: float = 60.0
    prev_sleep: float = 1.0

    def __call__(self, attempt: int) -> float:
        sleep: float = min(self.cap, random.uniform(self.base, self.prev_sleep * 3))
        self.prev_sleep = sleep
        return sleep


@dataclass(frozen=True, slots=True)
class FibonacciBackoff:
    base: float = 1.0

    def __call__(self, attempt: int) -> float:
        a: int
        b: int
        a, b = 0, 1
        for _ in range(attempt):
            a, b = b, a + b
        return a * self.base


@dataclass(frozen=True, slots=True)
class TruncatedExponentialBackoff:
    base: float = 2.0
    initial: float = 1.0
    cap: float = 60.0

    def __call__(self, attempt: int) -> float:
        return min(self.cap, self.initial * (self.base**attempt))
