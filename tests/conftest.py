from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture


@pytest.fixture
def sync_callback() -> MagicMock:
    return MagicMock(return_value=None)


@pytest.fixture
def async_callback() -> AsyncMock:
    return AsyncMock(return_value=None)


@pytest.fixture
def patch_sleep(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("pytryagain._retry.time.sleep")


@pytest.fixture
def patch_async_sleep(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch("pytryagain._retry.asyncio.sleep", new_callable=AsyncMock)
