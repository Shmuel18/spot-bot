import pytest
from unittest.mock import AsyncMock
from decimal import Decimal
from bot.logic.trade_manager import round_step_size, round_tick_size, get_total_balance


@pytest.mark.asyncio
async def test_round_step_size():
    qty = Decimal('1.23456789')
    step_size = '0.01'
    result = await round_step_size(qty, step_size)
    assert result == Decimal('1.23')


@pytest.mark.asyncio
async def test_round_tick_size():
    price = Decimal('123.456789')
    tick_size = '0.01'
    result = await round_tick_size(price, tick_size)
    assert result == Decimal('123.45')


@pytest.mark.asyncio
async def test_get_total_balance():
    client = AsyncMock()
    # דימוי תגובת חשבון עם יתרת USDT
    client.get_account.return_value = {
        'balances': [{'asset': 'USDT', 'free': '1000.0', 'locked': '0.0'}]
    }
    # דימוי מחיר שוק נוכחי עבור הנכסים הפתוחים
    client.get_ticker.return_value = [{'symbol': 'BTCUSDT', 'lastPrice': '50000.0'}]
    
    config = {}
    open_trades = {'BTCUSDT': {'quantity': Decimal('0.02')}}
    
    result = await get_total_balance(client, config, open_trades)
    # 1000 USDT + (0.02 BTC * 50000) = 2000 USDT
    expected = Decimal('1000.0') + Decimal('0.02') * Decimal('50000.0')
    assert result == expected