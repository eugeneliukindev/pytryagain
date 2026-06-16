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

        @retry(tries=3, default_backoff=_BACKOFF)
        def unstable_func() -> int:
            return mock_func()

        result = unstable_func()

        assert result == 99
        assert patch_sleep.call_count == 2

    def test_exhausts_tries_and_raises(self, patch_sleep: MagicMock) -> None:
        @retry(tries=3, default_backoff=_BACKOFF)
        def always_fails() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            always_fails()

        assert patch_sleep.call_count == 2

    def test_non_matching_exception_propagates_immediately(self, patch_sleep: MagicMock) -> None:
        @retry(tries=3, default_backoff=_BACKOFF, exceptions=(TypeError,))
        def raises_value_error() -> None:
            raise ValueError("not retried")

        with pytest.raises(ValueError, match="not retried"):
            raises_value_error()

        patch_sleep.assert_not_called()

    def test_calls_exception_callback_on_each_retry(self, sync_callback: MagicMock) -> None:
        call_count = 0

        @retry(tries=3, default_backoff=_BACKOFF, on_exception_callback=sync_callback)
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
        @retry(tries=2, default_backoff=_BACKOFF, on_giveup_callback=sync_callback)
        def always_fails() -> None:
            raise ValueError("done")

        with pytest.raises(ValueError):
            always_fails()

        sync_callback.assert_called_once()
        exc, attempt = sync_callback.call_args[0]
        assert isinstance(exc, ValueError)
        assert attempt == 2

    def test_no_giveup_callback_still_raises(self) -> None:
        @retry(tries=2, default_backoff=_BACKOFF)
        def always_fails() -> None:
            raise RuntimeError("bare")

        with pytest.raises(RuntimeError, match="bare"):
            always_fails()

    def test_retry_if_exception_stops_on_false(self, patch_sleep: MagicMock) -> None:
        @retry(tries=5, default_backoff=_BACKOFF, retry_if_exception=lambda _: False)
        def always_fails() -> None:
            raise ValueError("stop")

        with pytest.raises(ValueError, match="stop"):
            always_fails()

        patch_sleep.assert_not_called()

    def test_timeout_stops_retrying(self, mocker: MockerFixture, patch_sleep: MagicMock) -> None:
        mocker.patch("pytryagain._utils.time.monotonic", side_effect=[0.0, 100.0])

        @retry(tries=5, default_backoff=_BACKOFF, timeout=30.0)
        def always_fails() -> None:
            raise ValueError("timeout")

        with pytest.raises(ValueError, match="timeout"):
            always_fails()

        patch_sleep.assert_not_called()

    def test_raises_for_async_exception_callback(self) -> None:
        with pytest.raises(TypeError, match="async on_exception_callback"):
            retry(tries=2, on_exception_callback=AsyncMock())(lambda: None)

    def test_raises_for_async_giveup_callback(self) -> None:
        with pytest.raises(TypeError, match="async on_giveup_callback"):
            retry(tries=2, on_giveup_callback=AsyncMock())(lambda: None)


class TestRetryIfException:
    def test_retries_when_predicate_returns_true(self, patch_sleep: MagicMock) -> None:
        call_count = 0

        @retry(tries=3, default_backoff=_BACKOFF, retry_if_exception=lambda e: isinstance(e, ValueError))
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
        @retry(tries=5, default_backoff=_BACKOFF, retry_if_exception=lambda e: not isinstance(e, RuntimeError))
        def raises_runtime_error() -> None:
            raise RuntimeError("do not retry")

        with pytest.raises(RuntimeError, match="do not retry"):
            raises_runtime_error()

        patch_sleep.assert_not_called()

    def test_calls_giveup_callback_when_predicate_stops_retry(self, sync_callback: MagicMock) -> None:
        @retry(
            tries=5,
            default_backoff=_BACKOFF,
            retry_if_exception=lambda _: False,
            on_giveup_callback=sync_callback,
        )
        def always_fails() -> None:
            raise ValueError("fatal")

        with pytest.raises(ValueError):
            always_fails()

        sync_callback.assert_called_once()


class TestRetryIfResult:
    def test_retries_when_result_predicate_returns_true(self, patch_sleep: MagicMock) -> None:
        call_count = 0

        @retry(tries=3, default_backoff=_BACKOFF, retry_if_result=lambda x: x != 42)
        def eventually_returns_42() -> int:
            nonlocal call_count
            call_count += 1
            return 42 if call_count >= 3 else 0

        result = eventually_returns_42()

        assert result == 42
        assert patch_sleep.call_count == 2

    def test_returns_last_result_when_tries_exhausted(self, patch_sleep: MagicMock) -> None:
        @retry(tries=3, default_backoff=_BACKOFF, retry_if_result=lambda x: x != 42)
        def always_returns_zero() -> int:
            return 0

        result = always_returns_zero()

        assert result == 0
        assert patch_sleep.call_count == 2

    def test_accepts_result_immediately_when_predicate_false(self, patch_sleep: MagicMock) -> None:
        @retry(tries=5, default_backoff=_BACKOFF, retry_if_result=lambda x: x < 0)
        def returns_positive() -> int:
            return 10

        result = returns_positive()

        assert result == 10
        patch_sleep.assert_not_called()

    def test_result_predicate_with_complex_object(self, patch_sleep: MagicMock) -> None:
        class Response:
            def __init__(self, status: int) -> None:
                self.status = status

        call_count = 0

        @retry(tries=3, default_backoff=_BACKOFF, retry_if_result=lambda r: r.status == 503)
        def fetch() -> Response:
            nonlocal call_count
            call_count += 1
            return Response(503 if call_count < 3 else 200)

        result = fetch()

        assert result.status == 200
        assert patch_sleep.call_count == 2

    def test_timeout_stops_result_retry(self, mocker: MockerFixture, patch_sleep: MagicMock) -> None:
        mocker.patch("pytryagain._retry._is_timed_out", return_value=True)

        @retry(tries=5, default_backoff=_BACKOFF, timeout=30.0, retry_if_result=lambda x: x != 42)
        def always_returns_zero() -> int:
            return 0

        result = always_returns_zero()

        assert result == 0
        patch_sleep.assert_not_called()

    async def test_async_timeout_stops_result_retry(self, mocker: MockerFixture, patch_async_sleep: AsyncMock) -> None:
        mocker.patch("pytryagain._retry._is_timed_out", return_value=True)

        @retry(tries=5, default_backoff=_BACKOFF, timeout=30.0, retry_if_result=lambda x: x != 42)
        async def always_returns_zero() -> int:
            return 0

        result = await always_returns_zero()

        assert result == 0
        patch_async_sleep.assert_not_called()

    async def test_async_retries_when_result_predicate_returns_true(self, patch_async_sleep: AsyncMock) -> None:
        call_count = 0

        @retry(tries=3, default_backoff=_BACKOFF, retry_if_result=lambda x: x != 99)
        async def eventually_returns_99() -> int:
            nonlocal call_count
            call_count += 1
            return 99 if call_count >= 3 else 0

        result = await eventually_returns_99()

        assert result == 99
        assert patch_async_sleep.call_count == 2

    async def test_async_returns_last_result_when_tries_exhausted(self, patch_async_sleep: AsyncMock) -> None:
        @retry(tries=3, default_backoff=_BACKOFF, retry_if_result=lambda x: x != 42)
        async def always_returns_zero() -> int:
            return 0

        result = await always_returns_zero()

        assert result == 0
        assert patch_async_sleep.call_count == 2


class TestBackoffByException:
    def test_uses_exception_specific_backoff(self, mocker: MockerFixture) -> None:
        sleep_mock = mocker.patch("pytryagain._retry.time.sleep")
        specific_backoff = ConstantBackoff(delay=5.0)
        call_count = 0

        @retry(
            tries=2,
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
            tries=2,
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
            tries=2,
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
    def test_raises_for_tries_less_than_one(self) -> None:
        with pytest.raises(ValueError, match="tries must be >= 1"):
            retry(tries=0)(lambda: None)

    def test_raises_for_tries_not_int(self) -> None:
        with pytest.raises(TypeError, match="tries must be int"):
            retry(tries=1.5)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_tries_bool(self) -> None:
        with pytest.raises(TypeError, match="tries must be int"):
            retry(tries=True)(lambda: None)  # type: ignore[arg-type]

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

    def test_raises_for_retry_if_exception_not_callable(self) -> None:
        with pytest.raises(TypeError, match="retry_if_exception must be callable"):
            retry(retry_if_exception="not_callable")(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_retry_if_result_not_callable(self) -> None:
        with pytest.raises(TypeError, match="retry_if_result must be callable"):
            retry(retry_if_result=42)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_on_exception_callback_not_callable(self) -> None:
        with pytest.raises(TypeError, match="on_exception_callback must be callable"):
            retry(on_exception_callback=123)(lambda: None)  # type: ignore[arg-type]

    def test_raises_for_on_giveup_callback_not_callable(self) -> None:
        with pytest.raises(TypeError, match="on_giveup_callback must be callable"):
            retry(on_giveup_callback=123)(lambda: None)  # type: ignore[arg-type]


class TestDecoratorFactory:
    def test_factory_mode(self) -> None:
        decorator = retry(tries=2, default_backoff=_BACKOFF)

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

        @retry(tries=3, default_backoff=_BACKOFF)
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
        @retry(tries=3, default_backoff=_BACKOFF)
        async def always_fails() -> None:
            raise ValueError("async boom")

        with pytest.raises(ValueError, match="async boom"):
            await always_fails()

        assert patch_async_sleep.call_count == 2

    async def test_sync_exception_callback(self, sync_callback: MagicMock) -> None:
        call_count = 0

        @retry(tries=3, default_backoff=_BACKOFF, on_exception_callback=sync_callback)
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

        @retry(tries=3, default_backoff=_BACKOFF, on_exception_callback=async_callback)
        async def fails_twice() -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("async cb")
            return 1

        await fails_twice()

        assert async_callback.call_count == 2

    async def test_sync_giveup_callback(self, sync_callback: MagicMock) -> None:
        @retry(tries=2, default_backoff=_BACKOFF, on_giveup_callback=sync_callback)
        async def always_fails() -> None:
            raise ValueError("giveup")

        with pytest.raises(ValueError):
            await always_fails()

        sync_callback.assert_called_once()

    async def test_async_giveup_callback(self, async_callback: AsyncMock) -> None:
        @retry(tries=2, default_backoff=_BACKOFF, on_giveup_callback=async_callback)
        async def always_fails() -> None:
            raise ValueError("async giveup")

        with pytest.raises(ValueError):
            await always_fails()

        async_callback.assert_called_once()

    async def test_no_giveup_callback_still_raises(self) -> None:
        @retry(tries=2, default_backoff=_BACKOFF)
        async def always_fails() -> None:
            raise RuntimeError("no cb")

        with pytest.raises(RuntimeError, match="no cb"):
            await always_fails()

    async def test_retry_if_exception_stops_on_false(self, patch_async_sleep: AsyncMock) -> None:
        @retry(tries=5, default_backoff=_BACKOFF, retry_if_exception=lambda _: False)
        async def always_fails() -> None:
            raise ValueError("stop async")

        with pytest.raises(ValueError, match="stop async"):
            await always_fails()

        patch_async_sleep.assert_not_called()
