from pytryagain._sentinel import _MISSING, _Sentinel


def test_sentinel_is_singleton() -> None:
    first = _Sentinel()
    second = _Sentinel()

    assert first is second


def test_missing_is_sentinel_instance() -> None:
    assert isinstance(_MISSING, _Sentinel)
