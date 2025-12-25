import asyncio
import logging
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from bot.database.database_service import insert_order, update_trade_status, update_trade_tp_order_id
from bot.utils.retry import retry

logger = logging.getLogger(__name__)

@retry(max_retries=3, backoff_factor=2)
async def get_available_balance(client: AsyncClient, asset: str = 'USDT') -> float:
    '''
    Retrieves the available balance for a given asset from Binance.
    '''
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
async def get_total_balance(client: AsyncClient, config: dict) -> float:
    '''
    Retrieves the total balance in USDT equivalent from Binance.
    '''
    try:
        account = await client.get_account()
        balances = account['balances']
        total_balance = 0.0
        for balance in balances:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total_asset = free + locked
            if asset == 'USDT':
                total_balance += total_asset
            elif total_asset > 0 and asset in config['balance_assets']:  # common pairs
                try:
                    ticker = await client.get_ticker(symbol=asset + 'USDT')
                    price = float(ticker['lastPrice'])
                    total_balance += total_asset * price
                except:
                    pass  # ignore if no pair
        return total_balance
    except BinanceAPIException as e:
        logger.error(f"Error getting total balance: {e}")
        return 0.0
async def get_symbol_info(client: AsyncClient, symbol: str) -> dict | None:
    '''
    Retrieves symbol information from Binance.
    '''
    try:
        exchange_info = await client.get_exchange_info()
        symbols_info = exchange_info['symbols']
        
        for symbol_info in symbols_info:
            if symbol_info['symbol'] == symbol:
                return symbol_info
        return None

    except BinanceAPIException as e:
        logger.error(f"Error getting symbol info for {symbol}: {e}")
        return None

async def round_quantity(quantity: float, step_size: str) -> float:
    try:
        decimal_places = 0
        step_size_decimal = float(step_size)
        while step_size_decimal < 1:
            step_size_decimal *= 10
            decimal_places += 1
        return round(quantity, decimal_places)
    except Exception as e:
        logger.error(f"Error rounding quantity: {e}")
        return 0.0

async def round_price(price: float, tick_size: str) -> float:
    try:
        decimal_places = 0
        tick_size_decimal = float(tick_size)
        while tick_size_decimal < 1:
            tick_size_decimal *= 10
            decimal_places += 1
        return round(price, decimal_places)
    except Exception as e:
        logger.error(f"Error rounding price: {e}")
        return 0.0

@retry(max_retries=3, backoff_factor=2)
async def open_trade(client: AsyncClient, symbol: str, config: dict) ->  dict | None:
    '''
    Opens a trade for a given symbol.
    '''
    symbol_info = await get_symbol_info(client, symbol)
    if not symbol_info:
        logger.error(f"Could not retrieve symbol info for {symbol}")
        return None

    # Determine quantity (position_size_percent of available USDT balance)
    available_balance = await get_available_balance(client)
    quantity = available_balance * (config['position_size_percent'] / 100)

    # Apply precision guard (round quantity to step size)
    step_size = symbol_info['filters'][2]['stepSize']
    quantity = await round_quantity(quantity, step_size)

    # Place market buy order
    try:
        order = await client.order_market_buy(symbol=symbol, quantity=quantity)
        logger.info(f"Placed market buy order for {symbol}: {order}")

        # Get current price for take profit calculation
        ticker = await client.get_ticker(symbol=symbol)
        avg_price = float(ticker['lastPrice'])

        return {"order": order, "quantity": quantity, "avg_price": avg_price}
    except BinanceAPIException as e:
        logger.error(f"Error opening trade for {symbol}: {e}")
        return None

@retry(max_retries=3, backoff_factor=2)
async def place_take_profit_order(client: AsyncClient, symbol: str, quantity: float, avg_price: float, config: dict) -> dict | None:
    '''
    Places a take profit order for a given symbol.
    '''
    try:
        # Calculate take profit price
        tp_percent = config['tp_percent'] / 100
        tp_price = avg_price * (1 + tp_percent)

        # Get symbol info for tick size
        symbol_info = await get_symbol_info(client, symbol)
        if symbol_info:
            tick_size = symbol_info['filters'][0]['tickSize']
            tp_price = await round_price(tp_price, tick_size)

        # Place limit sell order
        order = await client.order_limit_sell(symbol=symbol, quantity=quantity, price=tp_price)
        logger.info(f"Placed take profit order for {symbol}: {order}")

        return order

    except Exception as e:
        logger.error(f"Error placing take profit order for {symbol}: {e}")
        return None

@retry(max_retries=3, backoff_factor=2)
async def dca(client: AsyncClient, symbol: str, config: dict, current_quantity: float, current_avg_price: float, trade_id: int, tp_order_id: str, dca_count: int) -> dict | None:
    '''
    Performs Dollar-Cost Averaging (DCA) for a given symbol.
    Returns a dict with tp_order, new_avg_price, new_quantity if successful.
    '''
    try:
        # Cancel existing take profit order
        logger.info(f"Cancelling existing take profit order {tp_order_id} for {symbol}")
        try:
            await client.cancel_order(symbol=symbol, orderId=tp_order_id)
        except BinanceAPIException as e:
            logger.error(f"Error cancelling take profit order {tp_order_id} for {symbol}: {e}")

        # Get symbol info
        symbol_info = await get_symbol_info(client, symbol)
        if not symbol_info:
            logger.error(f"Could not retrieve symbol info for {symbol}")
            return None

        # Determine DCA quantity
        dca_scale = config['dca_scales'][dca_count] if dca_count < len(config['dca_scales']) else config['dca_scales'][-1]
        dca_quantity = current_quantity * dca_scale

        # Apply precision guard (round quantity to step size)
        step_size = symbol_info['filters'][2]['stepSize']
        dca_quantity = await round_quantity(dca_quantity, step_size)

        # Place market buy order
        dca_order = await client.order_market_buy(symbol=symbol, quantity=dca_quantity)
        logger.info(f"Placed DCA order for {symbol}: {dca_order}")
        await insert_order(trade_id, dca_order['orderId'], 'DCA', 0, dca_quantity, dca_order['status'])

        # Calculate new average price
        ticker = await client.get_ticker(symbol=symbol)
        current_price = float(ticker['lastPrice'])
        new_avg_price = (current_avg_price * current_quantity + current_price * dca_quantity) / (current_quantity + dca_quantity)
        new_quantity = current_quantity + dca_quantity

        # Place new take profit order
        tp_order = await place_take_profit_order(client, symbol, new_quantity, new_avg_price, config)
        if tp_order:
            logger.info(f"Placed new take profit order for {symbol}: {tp_order}")
            await insert_order(trade_id, tp_order['orderId'], 'TP', tp_order['price'], tp_order['origQty'], tp_order['status'])
            await update_trade_tp_order_id(trade_id, tp_order['orderId'])
            return {'tp_order': tp_order, 'new_avg_price': new_avg_price, 'new_quantity': new_quantity}
        else:
            logger.error(f"Failed to place new take profit order for {symbol}")
            return None

    except BinanceAPIException as e:
        logger.error(f"Error performing DCA for {symbol}: {e}")
        return None
