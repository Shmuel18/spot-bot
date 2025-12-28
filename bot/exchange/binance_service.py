import logging
from binance import AsyncClient
from bot.utils.retry import retry

logger = logging.getLogger(__name__)


@retry(max_retries=3, backoff_factor=2)
async def get_usdt_pairs(client: AsyncClient, config: dict):
    """
    Retrieves a list of USDT pairs from Binance, filtering out stablecoins and leveraged tokens.
    """
    try:
        exchange_info = await client.get_exchange_info()
        symbols = exchange_info["symbols"]

        blacklist = config.get("blacklist", [])
        usdt_pairs = [
            symbol["symbol"]
            for symbol in symbols
            if symbol["quoteAsset"] == "USDT" and not any(blacklisted in symbol["symbol"] for blacklisted in blacklist)
        ]

        logger.info(f"Found {len(usdt_pairs)} USDT pairs.")
        return usdt_pairs

    except Exception as e:
        logger.error(f"Error retrieving USDT pairs: {e}")
        return []


@retry(max_retries=3, backoff_factor=2)
async def filter_by_volume(client: AsyncClient, symbols: list, min_volume: float):
    """
    Filters a list of symbols based on their 24h trading volume.
    """
    try:
        ticker_stats = await client.get_ticker(symbols=symbols)

        filtered_symbols = [item["symbol"] for item in ticker_stats if float(item["volume"]) >= min_volume]

        logger.info(f"Filtered {len(filtered_symbols)} symbols with volume >= {min_volume} USDT.")
        return filtered_symbols

    except Exception as e:
        logger.error(f"Error filtering symbols by volume: {e}")
        return []


@retry(max_retries=3, backoff_factor=2)
async def get_order(client: AsyncClient, symbol: str, order_id: str):
    """
    Retrieves order details from Binance.
    """
    try:
        order = await client.get_order(symbol=symbol, orderId=order_id)
        logger.info(f"Retrieved order details for {symbol} orderId {order_id}")
        return order
    except Exception as e:
        logger.error(f"Error retrieving order details for {symbol} orderId {order_id}: {e}")
        return None
