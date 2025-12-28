import pytest
from unittest.mock import AsyncMock
from decimal import Decimal
from bot.logic.trade_manager import round_quantity, round_price, get_total_balance


@pytest.mark.asyncio
async def test_round_quantity():
    qty = Decimal('1.23456789')
    step_size = '0.01'
    result = await round_quantity(qty, step_size)
    assert result == Decimal('1.23')


@pytest.mark.asyncio
async def test_round_price():
    price = Decimal('123.456789')
    tick_size = '0.01'
    result = await round_price(price, tick_size)
    assert result == Decimal('123.45')


@pytest.mark.asyncio
async def test_get_total_balance():
    client = AsyncMock()
    client.get_account.return_value = {
        'balances': [{'asset': 'USDT', 'free': '1000.0', 'locked': '0.0'}]
    }
    client.get_ticker.return_value = [{'symbol': 'BTCUSDT', 'lastPrice': '50000.0'}]
    
    config = {}
    open_trades = {'BTCUSDT': {'quantity': Decimal('0.02')}}
    
    result = await get_total_balance(client, config, open_trades)
    expected = Decimal('1000.0') + Decimal('0.02') * Decimal('50000.0')
    assert result == expected