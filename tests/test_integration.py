import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from bot.main import TradingEngine
from bot.config_model import BotConfig

@pytest.mark.asyncio
async def test_trading_engine_initialization():
    # 1. קונפיגורציה למבחן
    config = BotConfig(
        timeframe='15m', sma_length=150,
        dip_threshold=Decimal("-3.0"), position_size_percent=Decimal("10"),
        tp_percent=Decimal("5"), dca_scales=[Decimal("1.0"), Decimal("1.5")],
        dca_trigger=Decimal("3.5"), max_positions=5,
        min_24h_volume=Decimal("1000000"), daily_loss_limit=Decimal("10"),
        sleep_interval=60, blacklist=[], dry_run=True
    )

    client = AsyncMock()
    
    # 2. אתחול המנוע
    engine = TradingEngine(config, client)

    # 3. Mock לשירותים חיצוניים (DB, WS, Telegram)
    with patch('bot.main.create_tables', new_callable=AsyncMock) as mock_create, \
         patch('bot.main.TradeRepository.get_open_trades', new_callable=AsyncMock) as mock_get_trades, \
         patch('bot.main.PriceCache.start', new_callable=AsyncMock) as mock_ws_start, \
         patch('bot.main.TelegramService.send_message', new_callable=AsyncMock) as mock_tg:
        
        mock_get_trades.return_value = [] 
        
        # 4. הרצה של ה-initialize
        await engine.initialize()

        # 5. בדיקות (Assertions)
        assert engine.running == True
        mock_create.assert_called_once()
        mock_get_trades.assert_called_once()
        mock_ws_start.assert_called_once()