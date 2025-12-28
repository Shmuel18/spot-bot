import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from bot.main import TradingEngine
from bot.config_model import BotConfig

@pytest.mark.asyncio
async def test_trading_engine_initialization():
    # 1. הכנת קונפיגורציה (שימוש ב-Decimal כפי שמוגדר במודל)
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
        blacklist=[]
    )

    # 2. Mock לקליינט של בינאנס
    client = AsyncMock()
    client.get_account.return_value = {
        "balances": [{"asset": "USDT", "free": "1000", "locked": "0"}]
    }
    
    # 3. אתחול המנוע
    engine = TradingEngine(config, client)

    # 4. Mock לשירותי ה-Database
    with patch('bot.main.create_tables', new_callable=AsyncMock) as mock_create, \
         patch('bot.main.TradeRepository.get_open_trades', new_callable=AsyncMock) as mock_get_trades:
        
        mock_get_trades.return_value = [] # אין עסקאות פתוחות בהתחלה
        
        # הרצת ה-initialize (עכשיו יקרא גם ל-create_tables וגם ל-reconcile)
        await engine.initialize()

        # 5. בדיקות (Assertions)
        assert engine.running == True
        assert engine.config.timeframe == '15m'
        
        # כעת הבדיקה הזו תעבור כי initialize קורא ל-create_tables
        mock_create.assert_called_once()
        mock_get_trades.assert_called_once()