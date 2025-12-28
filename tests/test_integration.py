import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from bot.main import TradingEngine
from bot.config_model import BotConfig

@pytest.mark.asyncio
async def test_trading_engine_initialization():
    """בדיקה שהאתחול עובר בצורה תקינה"""
    config = BotConfig(
        timeframe='15m', sma_length=150,
        dip_threshold=Decimal("-3.0"), position_size_percent=Decimal("10"),
        tp_percent=Decimal("5"), dca_scales=[Decimal("1.0"), Decimal("1.5")],
        dca_trigger=Decimal("3.5"), max_positions=5,
        min_24h_volume=Decimal("1000000"), daily_loss_limit=Decimal("10"),
        sleep_interval=60, blacklist=[], dry_run=True
    )

    client = AsyncMock()
    engine = TradingEngine(config, client)

    with patch('bot.main.create_tables', new_callable=AsyncMock), \
         patch('bot.main.TradeRepository.get_open_trades', new_callable=AsyncMock) as mock_get_trades, \
         patch('bot.main.PriceCache.start', new_callable=AsyncMock), \
         patch('bot.main.TelegramService.send_message', new_callable=AsyncMock):
        
        mock_get_trades.return_value = [] 
        await engine.initialize()

        assert engine.running == True
        mock_get_trades.assert_called_once()

@pytest.mark.asyncio
async def test_engine_skips_when_unhealthy():
    """בדיקה שהבוט מדלג על הלופ אם נתוני ה-WebSocket לא טריים"""
    config = MagicMock(spec=BotConfig)
    # הגדרת ערכים הכרחיים שהמנוע ניגש אליהם ישירות
    config.max_positions = 5
    config.sleep_interval = 60
    config.dca_scales = [Decimal("1.0")]
    config.blacklist = []
    config.min_24h_volume = Decimal("1000000")
    config.model_dump.return_value = {
        "max_positions": 5,
        "sleep_interval": 60,
        "dca_scales": [Decimal("1.0")],
        "min_24h_volume": Decimal("1000000"),
        "blacklist": []
    }

    client = AsyncMock()
    engine = TradingEngine(config, client)

    # פיתרון ל-TypeError: משתמשים ב-MagicMock עבור האובייקט, אבל הופכים רק את start ל-AsyncMock
    engine.price_cache = MagicMock()
    engine.price_cache.start = AsyncMock() # מאפשר לעשות await ב-initialize
    engine.price_cache.is_healthy.return_value = False # מחזיר False בוליאני פשוט

    with patch('bot.main.create_tables', new_callable=AsyncMock), \
         patch('bot.main.TradeRepository.get_open_trades', new_callable=AsyncMock) as mock_trades, \
         patch('bot.main.TelegramService.send_message', new_callable=AsyncMock), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:

        mock_trades.return_value = []
        
        # הגדרה שהלופ ייעצר אחרי ה-sleep הראשון של ה-health check
        mock_sleep.side_effect = lambda x: setattr(engine, 'running', False)
        engine.running = True

        await engine.run()

        # האסרציה צריכה להיות 1:
        # פעם אחת ב-initialize (דרך reconcile)
        # בתוך ה-run הוא אמור להיעצר ב-is_healthy() ולעשות continue מבלי לקרוא ל-get_open_trades בפעם השנייה
        assert mock_trades.call_count == 1
        # מוודא שהדילוג אכן קרה ושהוא ניסה לישון 10 שניות כמתוכנן
        mock_sleep.assert_called_with(10)