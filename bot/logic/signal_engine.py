import asyncio
import logging
from binance import AsyncClient

logger = logging.getLogger(__name__)

# Cache for SMA calculations
sma_cache = {}

async def get_sma_150(client: AsyncClient, symbol: str, config: dict):
    '''
    Gets the SMA(150) for a symbol, using cache if available.
    '''
    if symbol in sma_cache:
        # Update with latest candle
        try:
            latest_kline = await client.get_historical_klines(symbol, config['timeframe'], '1 minutes ago')
            if latest_kline:
                latest_close = float(latest_kline[0][4])
                # Simple update: replace oldest with latest (approximation)
                cached_klines = sma_cache[symbol]['klines']
                cached_klines.pop(0)
                cached_klines.append(latest_close)
                sma = sum(cached_klines) / len(cached_klines)
                sma_cache[symbol]['sma'] = sma
                return sma
        except Exception as e:
            logger.error(f"Error updating SMA cache for {symbol}: {e}")
    
    # Fetch full SMA_LENGTH candles
    try:
        klines_150 = await client.get_historical_klines(symbol, config['timeframe'], f"{config['sma_length']} * {config['timeframe']} ago")
        if not klines_150 or len(klines_150) < config['sma_length']:
            return None
        closes = [float(kline[4]) for kline in klines_150]
        sma = sum(closes) / len(closes)
        sma_cache[symbol] = {'klines': closes, 'sma': sma}
        return sma
    except Exception as e:
        logger.error(f"Error fetching SMA for {symbol}: {e}")
        return None

async def check_entry_conditions(client: AsyncClient, symbol: str, config: dict):
    '''
    Checks the entry conditions for a given symbol.
    '''
    try:
        # Get the last 15m candle
        klines = await client.get_historical_klines(symbol, config['timeframe'], '15 minutes ago')
        if not klines:
            logger.warning(f"Could not retrieve klines for {symbol}")
            return False
        last_candle = klines[0]
        close_price = float(last_candle[4])
        open_price = float(last_candle[1])
        candle_change = (close_price - open_price) / open_price * 100

        # Get the SMA(150)
        current_sma = await get_sma_150(client, symbol, config)
        if current_sma is None:
            logger.warning(f"Could not retrieve SMA(150) for {symbol}")
            return False

        # Check conditions
        dip_threshold = config['dip_threshold']
        if candle_change <= dip_threshold and close_price < current_sma:
            logger.info(f"Entry conditions met for {symbol}: candle_change={candle_change}, close_price={close_price}, sma_150={current_sma}")
            return True
        else:
            logger.debug(f"Entry conditions not met for {symbol}: candle_change={candle_change}, close_price={close_price}, sma_150={current_sma}")
            return False

    except Exception as e:
        logger.error(f"Error checking entry conditions for {symbol}: {e}")
        return False