import pytest
from unittest.mock import AsyncMock
from decimal import Decimal
from bot.logic.trade_manager import round_to_precision, get_total_balance

def test_round_to_precision_qty():
    # בדיקת עיגול כמות (Step Size)
    qty = Decimal('1.23456789')
    step_size = '0.01'
    result = round_to_precision(qty, step_size)
    assert result == Decimal('1.23')

def test_round_to_precision_price():
    # בדיקת עיגול מחיר (Tick Size)
    price = Decimal('123.456789')
    tick_size = '0.1'
    result = round_to_precision(price, tick_size)
    assert result == Decimal('123.4')

@pytest.mark.asyncio
async def test_get_total_balance():
    client = AsyncMock()
    # דימוי יתרה ב-USDT
    client.get_account.return_value = {
        'balances': [{'asset': 'USDT', 'free': '1000.0', 'locked': '0.0'}]
    }
    # דימוי מחיר שוק
    client.get_ticker.return_value = [{'symbol': 'BTCUSDT', 'lastPrice': '50000.0'}]
    
    config = {}
    # שימוש במבנה החדש של פוזיציות (רשימה של מילונים מה-DB)
    open_trades = [{'symbol': 'BTCUSDT', 'base_qty': Decimal('0.02')}]
    
    result = await get_total_balance(client, config, open_trades)
    
    # חישוב: 1000 + (0.02 * 50000) = 2000
    assert result == Decimal('2000.0')