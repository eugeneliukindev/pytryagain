from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from pytryagain import retry
from pytryagain.backoff import ConstantBackoff

_BACKOFF = ConstantBackoff(delay=0.0)


class TestSyncRetry:
    def test_succeeds_on_first_attempt(self, patch_sleep: MagicMock) -> None:
        @retry(backoff=_BACKOFF)
        def succeeding_func() -> int:
            return 42

        result = succeeding_func()

        assert result == 42
        patch_sleep.assert_not_called()

    def test_retries_then_succeeds(self, patch_sleep: MagicMock) -> None:
        mock_func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), 99])

        @retry(tries=3, backoff=_BACKOFF)
        def unstable_func() -> int:
            return mock_func()

        result = unstable_func()

        assert result == 99
        assert patch_sleep.call_count == 2

    def test_exhausts_tries_and_raises(self, patch_sleep: MagicMock) -> None:
        @retry(tries=3, backoff=_BACKOFF)
        def always_fails() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            always_fails()

        assert patch_sleep.call_count == 2

    def test_non_matching_exception_propagates_immediately(self, patch_sleep: MagicMock) -> None:
        @retry(tries=3, backoff=_BACKOFF, exceptions=(TypeError,))
        def raises_value_error() -> None:
            raise ValueError("not retried")

        with pytest.raises(ValueError, match="not retried"):
            raises_value_error()

        patch_sleep.assert_not_called()

    def test_calls_exception_callback_on_each_retry(self, sync_callback: MagicMock) -> None:
        call_count = 0

        @retry(tries=3, backoff=_BACKOFF, on_exception_callback=sync_callback)
        def fails_twice() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("retry me")
            return 1

        fails_twice()

        assert sync_callback.call_count == 2
        assert sync_callback.call_args_list[0][0][1] == 1
        assert sync_callback.call_args_list[1][0][1] == 2

    def test_calls_giveup_callback_on_final_failure(self, sync_callback: MagicMock) -> None:
        @retry(tries=2, backoff=_BACKOFF, on_giveup_callback=sync_callback)
        def always_fails() -> None:
            raise ValueError("done")

        with pytest.raises(ValueError):
            always_fails()

        sync_callback.assert_called_once()
        exc, attempt = sync_callback.call_args[0]
        assert isinstance(exc, ValueError)
        assert attempt == 2

    def test_no_giveup_callback_still_raises(self) -> None:
        @retry(tries=2, backoff=_BACKOFF)
        def always_fails() -> None:
            raise RuntimeError("bare")

        with pytest.raises(RuntimeError, match="bare"):
            always_fails()

    def test_retry_if_stops_on_false(self, patch_sleep: MagicMock) -> None:
        @retry(tries=5, backoff=_BACKOFF, retry_if=lambda _: False)
        def always_fails() -> None:
            raise ValueError("stop")

        with pytest.raises(ValueError, match="stop"):
            always_fails()

        patch_sleep.assert_not_called()

    def test_timeout_stops_retrying(self, mocker: MockerFixture, patch_sleep: MagicMock) -> None:
        mocker.patch("pytryagain._utils.time.monotonic", side_effect=[0.0, 100.0])

        @retry(tries=5, backoff=_BACKOFF, timeout=30.0)
        def always_fails() -> None:
            raise ValueError("timeout")

        with pytest.raises(ValueError, match="timeout"):
            always_fails()

        patch_sleep.assert_not_called()

    def test_raises_for_async_exception_callback(self) -> None:
        with pytest.raises(ValueError, match="async on_exception_callback"):
            retry(tries=2, on_exception_callback=AsyncMock())(lambda: None)

    def test_raises_for_async_giveup_callback(self) -> None:
        with pytest.raises(ValueError, match="async on_giveup_callback"):
            retry(tries=2, on_giveup_callback=AsyncMock())(lambda: None)


class TestValidation:
    def test_raises_for_tries_less_than_one(self) -> None:
        with pytest.raises(ValueError, match="tries must be an integer >= 1"):
            retry(tries=0)(lambda: None)

    def test_raises_for_tries_not_int(self) -> None:
        with pytest.raises(ValueError, match="tries must be an integer >= 1"):
            retry(tries=1.5)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_non_positive_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout must be a positive number"):
            retry(timeout=0.0)(lambda: None)

    def test_raises_for_empty_exceptions_tuple(self) -> None:
        with pytest.raises(ValueError, match="non-empty tuple"):
            retry(exceptions=())(lambda: None)

    def test_raises_for_non_exception_in_exceptions(self) -> None:
        with pytest.raises(ValueError, match="BaseException subclasses"):
            retry(exceptions=(str,))(lambda: None)  # type: ignore[arg-type]


class TestDecoratorFactory:
    def test_factory_mode(self) -> None:
        decorator = retry(tries=2, backoff=_BACKOFF)

        @decorator
        def always_fails() -> None:
            raise RuntimeError("factory")

        with pytest.raises(RuntimeError, match="factory"):
            always_fails()


class TestAsyncRetry:
    async def test_succeeds_on_first_attempt(self, patch_async_sleep: AsyncMock) -> None:
        @retry(backoff=_BACKOFF)
        async def succeeding_func() -> int:
            return 7

        result = await succeeding_func()

        assert result == 7
        patch_async_sleep.assert_not_called()

    async def test_retries_then_succeeds(self, patch_async_sleep: AsyncMock) -> None:
        call_count = 0

        @retry(tries=3, backoff=_BACKOFF)
        async def unstable_func() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("async fail")
            return 99

        result = await unstable_func()

        assert result == 99
        assert patch_async_sleep.call_count == 2

    async def test_exhausts_tries_and_raises(self, patch_async_sleep: AsyncMock) -> None:
        @retry(tries=3, backoff=_BACKOFF)
        async def always_fails() -> None:
            raise ValueError("async boom")

        with pytest.raises(ValueError, match="async boom"):
            await always_fails()

        assert patch_async_sleep.call_count == 2

    async def test_sync_exception_callback(self, sync_callback: MagicMock) -> None:
        call_count = 0

        @retry(tries=3, backoff=_BACKOFF, on_exception_callback=sync_callback)
        async def fails_twice() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("cb")
            return 1

        await fails_twice()

        assert sync_callback.call_count == 2

    async def test_async_exception_callback(self, async_callback: AsyncMock) -> None:
        call_count = 0

        @retry(tries=3, backoff=_BACKOFF, on_exception_callback=async_callback)
        async def fails_twice() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("async cb")
            return 1

        await fails_twice()

        assert async_callback.call_count == 2

    async def test_sync_giveup_callback(self, sync_callback: MagicMock) -> None:
        @retry(tries=2, backoff=_BACKOFF, on_giveup_callback=sync_callback)
        async def always_fails() -> None:
            raise ValueError("giveup")

        with pytest.raises(ValueError):
            await always_fails()

        sync_callback.assert_called_once()

    async def test_async_giveup_callback(self, async_callback: AsyncMock) -> None:
        @retry(tries=2, backoff=_BACKOFF, on_giveup_callback=async_callback)
        async def always_fails() -> None:
            raise ValueError("async giveup")

        with pytest.raises(ValueError):
            await always_fails()

        async_callback.assert_called_once()

    async def test_no_giveup_callback_still_raises(self) -> None:
        @retry(tries=2, backoff=_BACKOFF)
        async def always_fails() -> None:
            raise RuntimeError("no cb")

        with pytest.raises(RuntimeError, match="no cb"):
            await always_fails()

    async def test_retry_if_stops_on_false(self, patch_async_sleep: AsyncMock) -> None:
        @retry(tries=5, backoff=_BACKOFF, retry_if=lambda _: False)
        async def always_fails() -> None:
            raise ValueError("stop async")

        with pytest.raises(ValueError, match="stop async"):
            await always_fails()

        patch_async_sleep.assert_not_called()
