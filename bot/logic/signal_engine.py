import logging
from binance import AsyncClient

logger = logging.getLogger(__name__)

# Cache structure: { symbol: {'klines': [closes], 'last_timestamp': int} }
sma_cache = {}

async def get_sma_150(client: AsyncClient, symbol: str, config: dict):
    try:
        # קבלת הנר האחרון (הנוכחי שעדיין רץ)
        latest_klines = await client.get_historical_klines(symbol, config['timeframe'], "2 candles ago")
        if not latest_klines or len(latest_klines) < 2: return None
        
        current_candle_ts = latest_klines[-1][0]
        current_close = float(latest_klines[-1][4])

        if symbol in sma_cache:
            cache = sma_cache[symbol]
            # עדכון רק אם עברנו לנר חדש
            if current_candle_ts > cache['last_timestamp']:
                cache['klines'].pop(0)
                cache['klines'].append(current_close)
                cache['last_timestamp'] = current_candle_ts
            
            return sum(cache['klines']) / len(cache['klines'])

        # אתחול ראשוני של ה-Cache (150 נרות)
        limit = config['sma_length'] + 1
        full_klines = await client.get_historical_klines(symbol, config['timeframe'], limit=limit)
        if len(full_klines) < config['sma_length']: return None
        
        closes = [float(k[4]) for k in full_klines[:-1]] # כל הנרות שנסגרו
        sma_cache[symbol] = {
            'klines': closes,
            'last_timestamp': full_klines[-1][0]
        }
        return sum(closes) / len(closes)

    except Exception as e:
        logger.error(f"SMA error for {symbol}: {e}")
        return None

async def check_entry_conditions(client: AsyncClient, symbol: str, config: dict):
    try:
        klines = await client.get_historical_klines(symbol, config['timeframe'], limit=1)
        if not klines: return False
        
        close_p = float(klines[0][4])
        open_p = float(klines[0][1])
        change = (close_p - open_p) / open_p * 100

        sma = await get_sma_150(client, symbol, config)
        if sma is None: return False

        # תנאי כניסה: ירידה חדה מתחת לסף ה-Dip ומחיר מתחת ל-SMA150
        if change <= config['dip_threshold'] and close_p < sma:
            logger.info(f"SIGNAL Entry: {symbol} at {close_p} (SMA: {sma})")
            return True
            
        return False
    except Exception as e:
        logger.error(f"Entry check error {symbol}: {e}")
        return False