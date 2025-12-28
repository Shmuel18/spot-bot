import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from bot.main import TradingEngine
from bot.config_model import BotConfig

@pytest.mark.asyncio
async def test_trading_engine_initialization():
    # 1. קונפיגורציה
    config = BotConfig(
        timeframe='15m',
        sma_length=150,
        dip_threshold=Decimal("-3.0"),
        position_size_percent=Decimal("10"),
        tp_percent=Decimal("5"),
        dca_scales=[Decimal("1.0"), Decimal("1.5")],
        dca_trigger=Decimal("3.5"),
        max_positions=5,
        min_24h_volume=Decimal("1000000"),
        daily_loss_limit=Decimal("10"),
        sleep_interval=60,
        blacklist=[],
        dry_run=True # חשוב לטסט הזה כדי ש-reconcile ידלג על לוגיקת ה-API
    )

    client = AsyncMock()
    
    # 2. אתחול המנוע
    engine = TradingEngine(config, client)

    # 3. Mock לשירותי ה-Database - שימוש בנתיב מלא ומדויק
    with patch('bot.main.create_tables', new_callable=AsyncMock) as mock_create, \
         patch('bot.main.TradeRepository.get_open_trades', new_callable=AsyncMock) as mock_get_trades:
        
        mock_get_trades.return_value = [] 
        
        # 4. הרצה
        await engine.initialize()

        # 5. בדיקות
        assert engine.running == True
        mock_create.assert_called_once()
        mock_get_trades.assert_called_once()