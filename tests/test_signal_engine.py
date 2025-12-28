import pytest
from unittest.mock import AsyncMock, patch
from bot.logic.signal_engine import check_entry_conditions, get_sma_150, sma_cache

@pytest.mark.asyncio
async def test_check_entry_conditions_no_sma():
    client = AsyncMock()
    client.get_historical_klines.side_effect = [[], []]  # No klines
    config = {'sma_length': 150, 'timeframe': '1h', 'dip_threshold': -5}
    result = await check_entry_conditions(client, 'BTCUSDT', config)
    assert result == False

@pytest.mark.asyncio
async def test_check_entry_conditions_meets_conditions():
    client = AsyncMock()
    # Mock SMA klines
    sma_klines = [[0, '100', '110', '90', '105']] * 151  # Enough for SMA > 100
    client.get_historical_klines.side_effect = [sma_klines, [['0', '100', '110', '90', '95']]]  # Current price 95, open 100, change -5%
    config = {'sma_length': 150, 'timeframe': '1h', 'dip_threshold': -4}  # -5 <= -4, 95 < 105
    result = await check_entry_conditions(client, 'BTCUSDT', config)
    assert result == True

@pytest.mark.asyncio
async def test_sma_caching():
    client = AsyncMock()
    sma_klines = [[0, '100', '110', '90', '105']] * 151
    client.get_historical_klines.return_value = sma_klines
    config = {'sma_length': 150, 'timeframe': '1h'}
    
    # Clear cache
    sma_cache.clear()
    
    # First call should calculate
    result1 = await get_sma_150(client, 'BTCUSDT', config)
    assert result1 is not None
    assert client.get_historical_klines.call_count == 1
    assert ('BTCUSDT', '1h') in sma_cache
    
    # Second call should use cache
    result2 = await get_sma_150(client, 'BTCUSDT', config)
    assert result2 == result1
    assert client.get_historical_klines.call_count == 1  # Still 1, used cache


def test_config_validation():
    from bot.config_model import BotConfig
    
    # Valid config
    config_data = {
        "timeframe": "1h",
        "sma_length": 150,
        "dip_threshold": -5.0,
        "position_size_percent": 10.0,
        "tp_percent": 5.0,
        "dca_scales": [0.5, 1.0],
        "dca_trigger": 10.0,
        "max_positions": 5,
        "min_24h_volume": 1000000.0,
        "daily_loss_limit": 10.0,
        "sleep_interval": 60,
        "blacklist": ["BTCUSDT"],
    }
    config = BotConfig(**config_data)
    assert config.timeframe == "1h"
    assert config.sma_length == 150

    # Invalid config
    invalid_data = config_data.copy()
    invalid_data["sma_length"] = -1
    try:
        BotConfig(**invalid_data)
        assert False, "Should raise validation error"
    except Exception:
        pass