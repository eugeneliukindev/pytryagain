from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from pytryagain import retry
from pytryagain.backoff import ConstantBackoff

_BACKOFF = ConstantBackoff(delay=0.0)


class TestSyncRetry:
    def test_succeeds_on_first_attempt(self, patch_sleep: MagicMock) -> None:
        @retry(default_backoff=_BACKOFF)
        def succeeding_func() -> int:
            return 42

        result = succeeding_func()

        assert result == 42
        patch_sleep.assert_not_called()

    def test_retries_then_succeeds(self, patch_sleep: MagicMock) -> None:
        mock_func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), 99])

        @retry(max_attempts=3, default_backoff=_BACKOFF)
        def unstable_func() -> int:
            return mock_func()

        result = unstable_func()

        assert result == 99
        assert patch_sleep.call_count == 2

    def test_exhausts_tries_and_raises(self, patch_sleep: MagicMock) -> None:
        @retry(max_attempts=3, default_backoff=_BACKOFF)
        def always_fails() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            always_fails()

        assert patch_sleep.call_count == 2

    def test_non_matching_exception_propagates_immediately(self, patch_sleep: MagicMock) -> None:
        @retry(max_attempts=3, default_backoff=_BACKOFF, exceptions=(TypeError,))
        def raises_value_error() -> None:
            raise ValueError("not retried")

        with pytest.raises(ValueError, match="not retried"):
            raises_value_error()

        patch_sleep.assert_not_called()

    def test_calls_exception_callback_on_each_retry(self, sync_callback: MagicMock) -> None:
        call_count = 0

        @retry(max_attempts=3, default_backoff=_BACKOFF, on_retry_callback=sync_callback)
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

    def test_calls_give_up_callback_on_final_failure(self, sync_callback: MagicMock) -> None:
        @retry(max_attempts=2, default_backoff=_BACKOFF, on_give_up_callback=sync_callback)
        def always_fails() -> None:
            raise ValueError("done")

        with pytest.raises(ValueError):
            always_fails()

        sync_callback.assert_called_once()
        exc, attempt = sync_callback.call_args[0]
        assert isinstance(exc, ValueError)
        assert attempt == 2

    def test_no_give_up_callback_still_raises(self) -> None:
        @retry(max_attempts=2, default_backoff=_BACKOFF)
        def always_fails() -> None:
            raise RuntimeError("bare")

        with pytest.raises(RuntimeError, match="bare"):
            always_fails()

    def test_should_retry_stops_on_false(self, patch_sleep: MagicMock) -> None:
        @retry(max_attempts=5, default_backoff=_BACKOFF, should_retry=lambda _: False)
        def always_fails() -> None:
            raise ValueError("stop")

        with pytest.raises(ValueError, match="stop"):
            always_fails()

        patch_sleep.assert_not_called()

    def test_timeout_stops_retrying(self, mocker: MockerFixture, patch_sleep: MagicMock) -> None:
        mocker.patch("pytryagain._utils.time.monotonic", side_effect=[0.0, 100.0])

        @retry(max_attempts=5, default_backoff=_BACKOFF, timeout=30.0)
        def always_fails() -> None:
            raise ValueError("timeout")

        with pytest.raises(ValueError, match="timeout"):
            always_fails()

        patch_sleep.assert_not_called()

    def test_raises_for_async_exception_callback(self) -> None:
        with pytest.raises(TypeError, match="async on_retry_callback"):
            retry(max_attempts=2, on_retry_callback=AsyncMock())(lambda: None)

    def test_raises_for_async_give_up_callback(self) -> None:
        with pytest.raises(TypeError, match="async on_give_up_callback"):
            retry(max_attempts=2, on_give_up_callback=AsyncMock())(lambda: None)


class TestRetryIfException:
    def test_retries_when_predicate_returns_true(self, patch_sleep: MagicMock) -> None:
        call_count = 0

        @retry(max_attempts=3, default_backoff=_BACKOFF, should_retry=lambda e: isinstance(e, ValueError))
        def fails_twice() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return call_count

        result = fails_twice()

        assert result == 3
        assert patch_sleep.call_count == 2

    def test_stops_immediately_when_predicate_returns_false(self, patch_sleep: MagicMock) -> None:
        @retry(max_attempts=5, default_backoff=_BACKOFF, should_retry=lambda e: not isinstance(e, RuntimeError))
        def raises_runtime_error() -> None:
            raise RuntimeError("do not retry")

        with pytest.raises(RuntimeError, match="do not retry"):
            raises_runtime_error()

        patch_sleep.assert_not_called()

    def test_calls_give_up_callback_when_predicate_stops_retry(self, sync_callback: MagicMock) -> None:
        @retry(
            max_attempts=5,
            default_backoff=_BACKOFF,
            should_retry=lambda _: False,
            on_give_up_callback=sync_callback,
        )
        def always_fails() -> None:
            raise ValueError("fatal")

        with pytest.raises(ValueError):
            always_fails()

        sync_callback.assert_called_once()


class TestBackoffByException:
    def test_uses_exception_specific_backoff(self, mocker: MockerFixture) -> None:
        sleep_mock = mocker.patch("pytryagain._retry.time.sleep")
        specific_backoff = ConstantBackoff(delay=5.0)
        call_count = 0

        @retry(
            max_attempts=2,
            default_backoff=_BACKOFF,
            backoff_by_exception={ValueError: specific_backoff},
        )
        def fails_once() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("specific")
            return 1

        fails_once()

        sleep_mock.assert_called_once_with(5.0)

    def test_falls_back_to_default_backoff_for_unmatched_exception(self, mocker: MockerFixture) -> None:
        sleep_mock = mocker.patch("pytryagain._retry.time.sleep")
        call_count = 0

        @retry(
            max_attempts=2,
            default_backoff=ConstantBackoff(delay=2.0),
            backoff_by_exception={TypeError: ConstantBackoff(delay=9.0)},
        )
        def fails_with_value_error() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("unmatched")
            return 1

        fails_with_value_error()

        sleep_mock.assert_called_once_with(2.0)

    def test_matches_exception_subclass(self, mocker: MockerFixture) -> None:
        sleep_mock = mocker.patch("pytryagain._retry.time.sleep")
        specific_backoff = ConstantBackoff(delay=7.0)
        call_count = 0

        @retry(
            max_attempts=2,
            default_backoff=_BACKOFF,
            backoff_by_exception={OSError: specific_backoff},
        )
        def fails_with_connection_error() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("subclass of OSError")
            return 1

        fails_with_connection_error()

        sleep_mock.assert_called_once_with(7.0)


class TestValidation:
    def test_raises_for_max_attempts_less_than_one(self) -> None:
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            retry(max_attempts=0)(lambda: None)

    def test_raises_for_max_attempts_not_int(self) -> None:
        with pytest.raises(TypeError, match="max_attempts must be int"):
            retry(max_attempts=1.5)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_max_attempts_bool(self) -> None:
        with pytest.raises(TypeError, match="max_attempts must be int"):
            retry(max_attempts=True)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_non_positive_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout must be > 0"):
            retry(timeout=0.0)(lambda: None)

    def test_raises_for_negative_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout must be > 0"):
            retry(timeout=-1.0)(lambda: None)

    def test_raises_for_timeout_bool(self) -> None:
        with pytest.raises(TypeError, match="timeout must be a positive number"):
            retry(timeout=True)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_empty_exceptions_tuple(self) -> None:
        with pytest.raises(ValueError, match="non-empty tuple"):
            retry(exceptions=())(lambda: None)

    def test_raises_for_exceptions_not_tuple(self) -> None:
        with pytest.raises(TypeError, match="exceptions must be a tuple"):
            retry(exceptions=[ValueError])(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_non_exception_in_exceptions(self) -> None:
        with pytest.raises(TypeError, match="BaseException subclasses"):
            retry(exceptions=(str,))(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_default_backoff_not_backoff(self) -> None:
        with pytest.raises(TypeError, match="default_backoff must implement BackOff protocol"):
            retry(default_backoff="fast")(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_backoff_by_exception_not_mapping(self) -> None:
        with pytest.raises(TypeError, match="backoff_by_exception must be a Mapping"):
            retry(backoff_by_exception="invalid")(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_backoff_by_exception_instance_key(self) -> None:
        with pytest.raises(TypeError, match="backoff_by_exception keys must be BaseException subclasses"):
            retry(backoff_by_exception={ValueError(): _BACKOFF})(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_backoff_by_exception_invalid_value(self) -> None:
        with pytest.raises(TypeError, match="backoff_by_exception values must implement BackOff protocol"):
            retry(backoff_by_exception={ValueError: "fast"})(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_should_retry_not_callable(self) -> None:
        with pytest.raises(TypeError, match="should_retry must be callable"):
            retry(should_retry="not_callable")(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_on_retry_callback_not_callable(self) -> None:
        with pytest.raises(TypeError, match="on_retry_callback must be callable"):
            retry(on_retry_callback=123)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_on_give_up_callback_not_callable(self) -> None:
        with pytest.raises(TypeError, match="on_give_up_callback must be callable"):
            retry(on_give_up_callback=123)(lambda: None)  # type: ignore[arg-type]


class TestDecoratorFactory:
    def test_factory_mode(self) -> None:
        decorator = retry(max_attempts=2, default_backoff=_BACKOFF)

        @decorator
        def always_fails() -> None:
            raise RuntimeError("factory")

        with pytest.raises(RuntimeError, match="factory"):
            always_fails()


class TestAsyncRetry:
    async def test_succeeds_on_first_attempt(self, patch_async_sleep: AsyncMock) -> None:
        @retry(default_backoff=_BACKOFF)
        async def succeeding_func() -> int:
            return 7

        result = await succeeding_func()

        assert result == 7
        patch_async_sleep.assert_not_called()

    async def test_retries_then_succeeds(self, patch_async_sleep: AsyncMock) -> None:
        call_count = 0

        @retry(max_attempts=3, default_backoff=_BACKOFF)
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
        @retry(max_attempts=3, default_backoff=_BACKOFF)
        async def always_fails() -> None:
            raise ValueError("async boom")

        with pytest.raises(ValueError, match="async boom"):
            await always_fails()

        assert patch_async_sleep.call_count == 2

    async def test_sync_exception_callback(self, sync_callback: MagicMock) -> None:
        call_count = 0

        @retry(max_attempts=3, default_backoff=_BACKOFF, on_retry_callback=sync_callback)
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

        @retry(max_attempts=3, default_backoff=_BACKOFF, on_retry_callback=async_callback)
        async def fails_twice() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("async cb")
            return 1

        await fails_twice()

        assert async_callback.call_count == 2

    async def test_sync_give_up_callback(self, sync_callback: MagicMock) -> None:
        @retry(max_attempts=2, default_backoff=_BACKOFF, on_give_up_callback=sync_callback)
        async def always_fails() -> None:
            raise ValueError("giveup")

        with pytest.raises(ValueError):
            await always_fails()

        sync_callback.assert_called_once()

    async def test_async_give_up_callback(self, async_callback: AsyncMock) -> None:
        @retry(max_attempts=2, default_backoff=_BACKOFF, on_give_up_callback=async_callback)
        async def always_fails() -> None:
            raise ValueError("async giveup")

        with pytest.raises(ValueError):
            await always_fails()

        async_callback.assert_called_once()

    async def test_no_give_up_callback_still_raises(self) -> None:
        @retry(max_attempts=2, default_backoff=_BACKOFF)
        async def always_fails() -> None:
            raise RuntimeError("no cb")

        with pytest.raises(RuntimeError, match="no cb"):
            await always_fails()

    async def test_should_retry_stops_on_false(self, patch_async_sleep: AsyncMock) -> None:
        @retry(max_attempts=5, default_backoff=_BACKOFF, should_retry=lambda _: False)
        async def always_fails() -> None:
            raise ValueError("stop async")

        with pytest.raises(ValueError, match="stop async"):
            await always_fails()

        patch_async_sleep.assert_not_called()
