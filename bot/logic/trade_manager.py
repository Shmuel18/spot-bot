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

@retry(max_retries=3, backoff_factor=2)
async def open_trade(client: AsyncClient, symbol: str, config: dict) ->  dict | None:
    '''
    Opens a trade for a given symbol.
    '''
    symbol_info = await get_symbol_info(client, symbol)
    if not symbol_info:
        logger.error(f"Could not retrieve symbol info for {symbol}")
        return None

    # Determine quantity (3% of available USDT balance)
    available_balance = await get_available_balance(client)
    quantity = available_balance * 0.03

    # Apply precision guard (round quantity to step size)
    step_size = symbol_info['filters'][2]['stepSize']
    quantity = await round_quantity(quantity, step_size)

        # Place aggressive limit buy order
    try:
        order = await client.order_limit_buy(symbol=symbol, quantity=quantity, price=0)
        logger.info(f"Placed aggressive limit buy order for {symbol}: {order}")

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

        # Place limit sell order
        order = await client.order_limit_sell(symbol=symbol, quantity=quantity, price=tp_price)
        logger.info(f"Placed take profit order for {symbol}: {order}")

        return order

    except Exception as e:
        logger.error(f"Error placing take profit order for {symbol}: {e}")
        return None

@retry(max_retries=3, backoff_factor=2)
async def dca(client: AsyncClient, symbol: str, config: dict, current_quantity: float, current_avg_price: float, trade_id: int, tp_order_id: str) -> dict | None:
    '''
    Performs Dollar-Cost Averaging (DCA) for a given symbol.
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

        # Determine DCA quantity (scale = 1.0 for the first DCA)
        dca_scale = config['dca_scales'][0]
        dca_quantity = current_quantity * dca_scale

        # Apply precision guard (round quantity to step size)
        step_size = symbol_info['filters'][2]['stepSize']
        dca_quantity = await round_quantity(dca_quantity, step_size)

        # Place aggressive limit buy order
        dca_order = await client.order_limit_buy(symbol=symbol, quantity=dca_quantity, price=0)
        logger.info(f"Placed DCA order for {symbol}: {dca_order}")
        await insert_order(trade_id, dca_order['orderId'], 'DCA', 0, dca_quantity, dca_order['status'])

        # Calculate new average price
        ticker = await client.get_ticker(symbol=symbol)
        current_price = float(ticker['lastPrice'])
        new_avg_price = (current_avg_price * current_quantity + current_price * dca_quantity) / (current_quantity + dca_quantity)

        # Place new take profit order
        tp_order = await place_take_profit_order(client, symbol, current_quantity + dca_quantity, new_avg_price, config)
        if tp_order:
            logger.info(f"Placed new take profit order for {symbol}: {tp_order}")
            await insert_order(trade_id, tp_order['orderId'], 'TP', tp_order['price'], tp_order['origQty'], tp_order['status'])
            await update_trade_tp_order_id(trade_id, tp_order['orderId'])
        else:
            logger.error(f"Failed to place new take profit order for {symbol}")

        return tp_order

    except BinanceAPIException as e):
        logger.error(f"Error performing DCA for {symbol}: {e}")
        return None
