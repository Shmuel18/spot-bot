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
        return [s["symbol"] for s in exchange_info["symbols"] 
                if s["quoteAsset"] == "USDT" 
                and s["status"] == "TRADING"
                and not any(b in s["symbol"] for b in blacklist)]
    except Exception as e:
        logger.error(f"Error USDT pairs: {e}")
        return []

@retry(max_retries=3)
async def filter_by_volume(client: AsyncClient, symbols: list, min_volume: float):
    """
    מבצע קריאה אחת לכל ה-Tickers ומסנן מקומית כדי לחסוך ב-API Weight
    """
    if not symbols: return []
    try:
        # קבלת כל הטיקרים בפעולה אחת (יעיל יותר)
        all_tickers = await client.get_ticker()
        symbol_set = set(symbols)
        
        filtered = [
            t["symbol"] for t in all_tickers 
            if t["symbol"] in symbol_set and float(t["quoteVolume"]) >= min_volume
        ]
        return filtered
    except Exception as e:
        logger.error(f"Error filtering by volume: {e}")
        return []

@retry(max_retries=3)
async def get_order(client: AsyncClient, symbol: str, order_id: str):
    try: 
        return await client.get_order(symbol=symbol, orderId=order_id)
    except Exception: 
        return None