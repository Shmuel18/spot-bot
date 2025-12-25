import asyncio
import logging
import math
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from bot.database.database_service import insert_order, update_trade_status, update_trade_tp_order_id
from bot.utils.retry import retry

logger = logging.getLogger(__name__)

def get_filter(symbol_info: dict, filter_type: str) -> dict | None:
    '''
    Helper to find a specific filter by type in symbol_info.
    '''
    for f in symbol_info.get('filters', []):
        if f['filterType'] == filter_type:
            return f
    return None

@retry(max_retries=3, backoff_factor=2)
async def get_available_balance(client: AsyncClient, asset: str = 'USDT') -> float:
    try:
        account = await client.get_account()
        balances = account['balances']
        for balance in balances:
            if balance['asset'] == asset:
                return float(balance['free'])
        return 0.0
    except BinanceAPIException as e:
        logger.error(f"Error getting available balance for {asset}: {e}")
        return 0.0

@retry(max_retries=3, backoff_factor=2)
async def get_total_balance(client: AsyncClient, config: dict, open_trades: dict) -> float:
    try:
        account = await client.get_account()
        balances = account['balances']
        total_balance = 0.0
        for balance in balances:
            asset = balance['asset']
            total_asset = float(balance['free']) + float(balance['locked'])
            if asset == 'USDT':
                total_balance += total_asset
            elif total_asset > 0 and asset in config.get('balance_assets', []):
                try:
                    ticker = await client.get_ticker(symbol=asset + 'USDT')
                    total_balance += total_asset * float(ticker['lastPrice'])
                except:
                    pass
        
        if open_trades:
            symbols = list(open_trades.keys())
            ticker_stats = await client.get_ticker(symbols=symbols)
            prices = {item['symbol']: float(item['lastPrice']) for item in ticker_stats}
            for symbol, trade_details in open_trades.items():
                current_price = prices.get(symbol, 0)
                unrealized_pnl = (current_price - trade_details['avg_price']) * trade_details['quantity']
                total_balance += unrealized_pnl
        return total_balance
    except Exception as e:
        logger.error(f"Error getting total balance: {e}")
        return 0.0

async def get_symbol_info(client: AsyncClient, symbol: str) -> dict | None:
    try:
        exchange_info = await client.get_exchange_info()
        for s in exchange_info['symbols']:
            if s['symbol'] == symbol:
                return s
        return None
    except Exception as e:
        logger.error(f"Error getting symbol info for {symbol}: {e}")
        return None

async def round_quantity(quantity: float, step_size: str) -> float:
    try:
        step_size_float = float(step_size)
        precision = int(round(-math.log10(step_size_float)))
        # Use floor to avoid "insufficient balance" errors
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor
    except Exception as e:
        logger.error(f"Error rounding quantity: {e}")
        return 0.0

async def round_price(price: float, tick_size: str) -> float:
    try:
        tick_size_float = float(tick_size)
        precision = int(round(-math.log10(tick_size_float)))
        return round(price, precision)
    except Exception as e:
        logger.error(f"Error rounding price: {e}")
        return price

@retry(max_retries=3, backoff_factor=2)
async def open_trade(client: AsyncClient, symbol: str, config: dict) -> dict | None:
    symbol_info = await get_symbol_info(client, symbol)
    if not symbol_info: return None

    available_balance = await get_available_balance(client)
    quantity_usdt = available_balance * (config['position_size_percent'] / 100)
    
    ticker = await client.get_ticker(symbol=symbol)
    price = float(ticker['lastPrice'])
    quantity = quantity_usdt / price

    lot_filter = get_filter(symbol_info, 'LOT_SIZE')
    if lot_filter:
        quantity = await round_quantity(quantity, lot_filter['stepSize'])

    try:
        if config.get('dry_run'):
            logger.info(f"DRY RUN: Buy {symbol} qty {quantity}")
            return {"order": {"orderId": "DRY_RUN"}, "quantity": quantity, "avg_price": price}
        
        order = await client.order_market_buy(symbol=symbol, quantity=quantity)
        return {"order": order, "quantity": quantity, "avg_price": price}
    except Exception as e:
        logger.error(f"Error opening trade for {symbol}: {e}")
        return None

@retry(max_retries=3, backoff_factor=2)
async def place_take_profit_order(client: AsyncClient, symbol: str, quantity: float, avg_price: float, config: dict) -> dict | None:
    try:
        tp_price = avg_price * (1 + (config['tp_percent'] / 100))
        symbol_info = await get_symbol_info(client, symbol)
        price_filter = get_filter(symbol_info, 'PRICE_FILTER')
        if price_filter:
            tp_price = await round_price(tp_price, price_filter['tickSize'])

        if config.get('dry_run'):
            return {"orderId": "DRY_TP", "status": "FILLED", "price": tp_price, "origQty": quantity}
        
        return await client.order_limit_sell(symbol=symbol, quantity=quantity, price=tp_price)
    except Exception as e:
        logger.error(f"Error placing TP for {symbol}: {e}")
        return None

@retry(max_retries=3, backoff_factor=2)
async def dca(client: AsyncClient, symbol: str, config: dict, current_quantity: float, current_avg_price: float, trade_id: int, tp_order_id: str, dca_count: int) -> dict | None:
    try:
        if not config.get('dry_run'):
            await client.cancel_order(symbol=symbol, orderId=tp_order_id)

        symbol_info = await get_symbol_info(client, symbol)
        dca_scale = config['dca_scales'][min(dca_count, len(config['dca_scales'])-1)]
        dca_quantity = current_quantity * dca_scale

        lot_filter = get_filter(symbol_info, 'LOT_SIZE')
        if lot_filter:
            dca_quantity = await round_quantity(dca_quantity, lot_filter['stepSize'])

        if config.get('dry_run'):
            dca_order = {"orderId": "DRY_DCA", "status": "FILLED"}
        else:
            dca_order = await client.order_market_buy(symbol=symbol, quantity=dca_quantity)

        await insert_order(trade_id, dca_order['orderId'], 'DCA', 0, dca_quantity, dca_order['status'])
        
        ticker = await client.get_ticker(symbol=symbol)
        curr_price = float(ticker['lastPrice'])
        new_qty = current_quantity + dca_quantity
        new_avg = ((current_avg_price * current_quantity) + (curr_price * dca_quantity)) / new_qty

        tp_order = await place_take_profit_order(client, symbol, new_qty, new_avg, config)
        if tp_order:
            await update_trade_tp_order_id(trade_id, tp_order['orderId'])
            return {'tp_order': tp_order, 'new_avg_price': new_avg, 'new_quantity': new_qty}
    except Exception as e:
        logger.error(f"DCA Error for {symbol}: {e}")
    return None