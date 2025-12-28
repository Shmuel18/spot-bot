import structlog
from binance import AsyncClient
from bot.utils.retry import retry
from bot.config_model import BotConfig

logger = structlog.get_logger(__name__)

@retry(max_retries=3)
async def get_usdt_pairs(client: AsyncClient, config: BotConfig):
    try:
        exchange_info = await client.get_exchange_info()
        blacklist = config.blacklist
        return [s["symbol"] for s in exchange_info["symbols"] if s["quoteAsset"] == "USDT" and not any(b in s["symbol"] for b in blacklist)]
    except Exception as e:
        logger.error(f"Error USDT pairs: {e}")
        return []

@retry(max_retries=3)
async def filter_by_volume(client: AsyncClient, symbols: list, min_volume: float):
    if not symbols: return [] # מונע שגיאה -1100
    try:
        tickers = await client.get_ticker(symbols=symbols)
        return [t["symbol"] for t in tickers if float(t["volume"]) >= min_volume]
    except Exception as e:
        logger.error(f"Error volume: {e}")
        return []

@retry(max_retries=3)
async def get_order(client: AsyncClient, symbol: str, order_id: str):
    try: return await client.get_order(symbol=symbol, orderId=order_id)
    except Exception: return None