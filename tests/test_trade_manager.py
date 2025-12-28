import pytest
from unittest.mock import AsyncMock
from decimal import Decimal
from bot.logic.trade_manager import round_to_precision, get_total_balance

@pytest.mark.asyncio
async def test_round_to_precision_qty():
    # בדיקת עיגול כמות (Step Size)
    qty = Decimal('1.23456789')
    step_size = '0.01'
    result = await round_to_precision(qty, step_size)
    assert result == Decimal('1.23')

@pytest.mark.asyncio
async def test_round_to_precision_price():
    # בדיקת עיגול מחיר (Tick Size)
    price = Decimal('123.456789')
    tick_size = '0.01'
    result = await round_to_precision(price, tick_size)
    assert result == Decimal('123.45')

@pytest.mark.asyncio
async def test_get_total_balance():
    client = AsyncMock()
    # דימוי יתרה ב-USDT
    client.get_account.return_value = {
        'balances': [{'asset': 'USDT', 'free': '1000.0', 'locked': '0.0'}]
    }
    # דימוי מחיר שוק עבור נכסים פתוחים
    client.get_ticker.return_value = [{'symbol': 'BTCUSDT', 'lastPrice': '50000.0'}]
    
    config = {}
    open_trades = {'BTCUSDT': {'quantity': Decimal('0.02')}}
    
    result = await get_total_balance(client, config, open_trades)
    
    # חישוב צפוי: 1000 USDT + (0.02 BTC * 50000) = 2000 USDT
    expected = Decimal('1000.0') + (Decimal('0.02') * Decimal('50000.0'))
    assert result == expected