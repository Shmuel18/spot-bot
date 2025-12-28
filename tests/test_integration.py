import pytest
from unittest.mock import AsyncMock
from bot.main import TradingEngine
from bot.config_model import BotConfig


@pytest.mark.asyncio
async def test_trading_engine_initialization():
    # Mock config
    config = BotConfig(
        timeframe='15m',
        sma_length=150,
        dip_threshold=-3.0,
        position_size_percent=10,
        tp_percent=5,
        dca_scales=[1.0, 1.5],
        dca_trigger=3.5,
        max_positions=5,
        min_24h_volume=1000000,
        daily_loss_limit=10,
        sleep_interval=60,
        blacklist=[]
    )

    # Mock client
    client = AsyncMock()
    client.get_open_orders.return_value = []
    client.get_account.return_value = {"balances": [{"asset": "USDT", "free": "1000", "locked": "0"}]}
    client.get_exchange_info.return_value = {"symbols": []}
    client.get_ticker.return_value = []

    # Mock telegram
    telegram = AsyncMock()

    engine = TradingEngine(config, client, telegram, "chat_id")

    # Mock database functions
    from bot.database import database_service
    database_service.create_tables = AsyncMock()
    database_service.get_open_trades = AsyncMock(return_value=[])

    # Mock binance service
    from bot.exchange import binance_service
    binance_service.get_usdt_pairs = AsyncMock(return_value=[])
    binance_service.filter_by_volume = AsyncMock(return_value=[])

    await engine.initialize()

    assert engine.open_trades == {}
    assert engine.symbols == []
    assert engine.daily_initial_equity == 1000