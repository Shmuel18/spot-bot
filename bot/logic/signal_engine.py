import asyncio
import logging
from binance import AsyncClient

logger = logging.getLogger(__name__)

# Cache for SMA calculations
# Structure: { symbol: {'klines': [closes], 'sma': float, 'last_timestamp': int} }
sma_cache = {}

async def get_sma_150(client: AsyncClient, symbol: str, config: dict):
    '''
    Gets the SMA(150) for a symbol, updates cache only on new candle closure.
    '''
    timeframe = config['timeframe']
    
    try:
        # Fetch only the latest closed candle to check for updates
        latest_klines = await client.get_historical_klines(symbol, timeframe, limit=2)
        if not latest_klines or len(latest_klines) < 2:
            return None
        
        # We look at the candle before the current "running" one (index -2 is the last closed)
        last_closed_candle = latest_klines[-2]
        last_ts = last_closed_candle[0]
        last_close = float(last_closed_candle[4])

        if symbol in sma_cache:
            if last_ts > sma_cache[symbol]['last_ts']:
                # New candle closed! Update cache
                closes = sma_cache[symbol]['klines']
                closes.pop(0)
                closes.append(last_close)
                sma = sum(closes) / len(closes)
                
                sma_cache[symbol] = {
                    'klines': closes,
                    'sma': sma,
                    'last_ts': last_ts
                }
                logger.info(f"SMA Cache updated for {symbol} (New candle TS: {last_ts})")
            return sma_cache[symbol]['sma']

        # If not in cache, fetch full history
        klines_full = await client.get_historical_klines(symbol, timeframe, limit=config['sma_length'] + 1)
        if len(klines_full) < config['sma_length'] + 1:
            return None
        
        # Use only closed candles (excluding the current live one)
        closed_only = klines_full[:-1]
        closes = [float(k[4]) for k in closed_only]
        sma = sum(closes) / len(closes)
        
        sma_cache[symbol] = {
            'klines': closes,
            'sma': sma,
            'last_ts': closed_only[-1][0]
        }
        return sma
        
    except Exception as e:
        logger.error(f"Error in SMA calculation for {symbol}: {e}")
        return None

async def check_entry_conditions(client: AsyncClient, symbol: str, config: dict):
    try:
        # Fetch the most recent closed candle
        klines = await client.get_historical_klines(symbol, config['timeframe'], limit=2)
        if not klines or len(klines) < 2:
            return False
            
        last_closed = klines[-2]
        close_price = float(last_closed[4])
        open_price = float(last_closed[1])
        candle_change = ((close_price - open_price) / open_price) * 100

        current_sma = await get_sma_150(client, symbol, config)
        if current_sma is None:
            return False

        if candle_change <= config['dip_threshold'] and close_price < current_sma:
            logger.info(f"SIGNAL: {symbol} change={candle_change:.2f}% < SMA={current_sma}")
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking entry for {symbol}: {e}")
        return False