import pytest
from unittest.mock import patch
from trade_binance.binance_api_warpper import BinanceAPIWrapper


@pytest.fixture
def binance_api_wrapper():
    """
    Fixture to provide an instance of BinanceAPIWrapper.
    """
    return BinanceAPIWrapper()


def test_my_exchange_info(binance_api_wrapper):
    """
    Test BinanceAPIWrapper().my_exchange_info by mocking the Binance API call.
    """
    mock_response = {
        'timezone': 'UTC',
        'serverTime': 1620000000000,
        'rateLimits': [],
        'exchangeFilters': [],
        'symbols': []
    }

    with patch.object(binance_api_wrapper.client, 'exchange_info', return_value=mock_response) as mock_exchange_info:
        response = binance_api_wrapper.my_exchange_info()

        # Assert that the mocked function was called once
        mock_exchange_info.assert_called_once()

        # Assert the response is as expected
        assert response == mock_response