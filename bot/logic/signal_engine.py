import asyncio
import logging
from binance import AsyncClient

logger = logging.getLogger(__name__)

async def check_entry_conditions(client: AsyncClient, symbol: str, config: dict):
    '''
    Checks the entry conditions for a given symbol.
    '''
    try:
        # Get the last 15m candle
        klines = await client.get_historical_klines(symbol, '15m', '15 minutes ago')
        if not klines:
            logger.warning(f"Could not retrieve klines for {symbol}")
            return False
        last_candle = klines[0]
        close_price = float(last_candle[4])
        open_price = float(last_candle[1])
        candle_change = (close_price - open_price) / open_price * 100

        # Get the SMA(150)
        klines_150 = await client.get_historical_klines(symbol, '15m', '150 * 15 minutes ago')
        if not klines_150 or len(klines_150) < 150:
            logger.warning(f"Could not retrieve enough klines for SMA(150) for {symbol}")
            return False
        sma_150 = sum([float(kline[4]) for kline in klines_150]) / len(klines_150)

        # Check conditions
        dip_threshold = config['dip_threshold']
        if candle_change <= dip_threshold and close_price < sma_150:
            logger.info(f"Entry conditions met for {symbol}: candle_change={candle_change}, close_price={close_price}, sma_150={sma_150}")
            return True
        else:
            logger.debug(f"Entry conditions not met for {symbol}: candle_change={candle_change}, close_price={close_price}, sma_150={sma_150}")
            return False

    except Exception as e:
        logger.error(f"Error checking entry conditions for {symbol}: {e}")
        return False