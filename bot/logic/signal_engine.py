import logging
from binance import AsyncClient

logger = logging.getLogger(__name__)
sma_cache = {}

async def get_sma_150(client: AsyncClient, symbol: str, config: dict):
    try:
        # קריאת נרות - נר אחד לפני הנוכחי כדי לוודא סגירה
        klines = await client.get_historical_klines(symbol, config['timeframe'], f"{config['sma_length'] + 1} candles ago")
        if len(klines) < config['sma_length']: return None
        
        closes = [float(k[4]) for k in klines[:-1]] # נרות סגורים בלבד
        return sum(closes) / len(closes)
    except Exception as e:
        logger.error(f"SMA calc error: {e}")
        return None

async def check_entry_conditions(client, symbol, config):
    try:
        sma = await get_sma_150(client, symbol, config)
        klines = await client.get_historical_klines(symbol, config['timeframe'], limit=1)
        if not sma or not klines: return False
        
        curr_price = float(klines[0][4])
        change = (curr_price - float(klines[0][1])) / float(klines[0][1]) * 100
        
        if change <= config['dip_threshold'] and curr_price < sma:
            return True
        return False
    except: return False