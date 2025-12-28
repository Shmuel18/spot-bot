import pytest
from unittest.mock import AsyncMock
from decimal import Decimal
from bot.logic.signal_engine import check_entry_conditions, get_sma, sma_cache
from bot.config_model import BotConfig

@pytest.mark.asyncio
async def test_check_entry_conditions_no_sma():
    client = AsyncMock()
    client.get_historical_klines.side_effect = [[], []]  # No klines
    config = {'sma_length': 150, 'timeframe': '1h', 'dip_threshold': Decimal('-5')}
    result = await check_entry_conditions(client, 'BTCUSDT', config)
    assert result == False

@pytest.mark.asyncio
async def test_check_entry_conditions_meets_conditions():
    client = AsyncMock()
    # Mock SMA klines: מחיר סגירה 105 לאורך 151 נרות
    sma_klines = [[0, '0', '0', '0', '105']] * 151 
    # Current kline: פתיחה 100, סגירה 95 -> ירידה של 5%
    current_kline = [['0', '100', '0', '0', '95']]
    client.get_historical_klines.side_effect = [sma_klines, current_kline]
    
    config = {'sma_length': 150, 'timeframe': '1h', 'dip_threshold': Decimal('-4')}
    # -5 <= -4 (תנאי ירידה מתקיים) וגם 95 < 105 (מתחת ל-SMA)
    result = await check_entry_conditions(client, 'BTCUSDT', config)
    assert result == True

@pytest.mark.asyncio
async def test_sma_caching():
    client = AsyncMock()
    sma_klines = [[0, '0', '0', '0', '105']] * 151
    client.get_historical_klines.return_value = sma_klines
    config = {'sma_length': 150, 'timeframe': '1h'}
    
    # Clear cache
    sma_cache.clear()
    
    # פעם ראשונה - חישוב מלא מול ה-API
    result1 = await get_sma(client, 'BTCUSDT', config)
    assert result1 is not None
    assert client.get_historical_klines.call_count == 1
    assert ('BTCUSDT', '1h') in sma_cache
    
    # פעם שנייה - שימוש ב-Cache (לא קורא ל-API)
    result2 = await get_sma(client, 'BTCUSDT', config)
    assert result2 == result1
    assert client.get_historical_klines.call_count == 1 

def test_config_validation():
    # בדיקת וולידציה של ה-Pydantic Model החדש
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
    assert isinstance(config.dip_threshold, Decimal)

    # בדיקת שגיאה בנתון לא תקין
    invalid_data = config_data.copy()
    invalid_data["sma_length"] = -1
    with pytest.raises(Exception):
        BotConfig(**invalid_data)