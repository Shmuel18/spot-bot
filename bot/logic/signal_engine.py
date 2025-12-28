import logging
from binance import AsyncClient
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

# Cache for SMA values: (symbol, timeframe) -> (sma_value, timestamp)
sma_cache: Dict[Tuple[str, str], Tuple[float, datetime]] = {}
CACHE_EXPIRY_MINUTES = 5  # Expire cache after 5 minutes


def parse_timeframe(timeframe: str) -> int:
    """
    Parse timeframe string to seconds.
    
    Examples: '15m' -> 900, '1h' -> 3600, '1d' -> 86400
    """
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    else:
        raise ValueError(f"Unsupported timeframe unit: {unit}")


async def get_sma_150(client: AsyncClient, symbol: str, config: dict) -> Optional[float]:
    """
    Calculate the 150-period SMA for a given symbol and timeframe.

    Uses caching to avoid redundant API calls. Cache expires after CACHE_EXPIRY_MINUTES.

    Args:
        client: Binance AsyncClient instance.
        symbol: Trading symbol (e.g., 'BTCUSDT').
        config: Configuration dictionary containing 'timeframe' and 'sma_length'.

    Returns:
        The SMA value or None if calculation fails.
    """
    cache_key = (symbol, config["timeframe"])
    now = datetime.now(timezone.utc)

    # Check cache
    if cache_key in sma_cache:
        cached_sma, cached_time = sma_cache[cache_key]
        if (now - cached_time).total_seconds() < CACHE_EXPIRY_MINUTES * 60:
            logger.debug(f"Using cached SMA for {symbol}: {cached_sma}")
            return cached_sma
        else:
            # Cache expired, remove it
            del sma_cache[cache_key]

    try:
        # Calculate seconds for sma_length candles
        timeframe_seconds = parse_timeframe(config["timeframe"])
        total_seconds = config["sma_length"] * timeframe_seconds
        start_str = (now - timedelta(seconds=total_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        klines = await client.get_historical_klines(symbol, config["timeframe"], start_str=start_str)
        if len(klines) < config["sma_length"]:
            return None

        closes = [float(k[4]) for k in klines[:-1]]  # Closed candles only
        sma = sum(closes) / len(closes)

        # Cache the result
        sma_cache[cache_key] = (sma, now)
        logger.debug(f"Calculated and cached SMA for {symbol}: {sma}")
        return sma
    except Exception as e:
        logger.error(f"SMA calc error for {symbol}: {e}")
        return None


async def check_entry_conditions(client: AsyncClient, symbol: str, config: dict) -> bool:
    """
    Check if entry conditions are met for a symbol.

    Conditions: Price drop from open >= dip_threshold and current price < SMA.

    Args:
        client: Binance AsyncClient instance.
        symbol: Trading symbol.
        config: Configuration dictionary.

    Returns:
        True if conditions are met, False otherwise.
    """
    try:
        sma = await get_sma_150(client, symbol, config)
        klines = await client.get_historical_klines(symbol, config["timeframe"], limit=1)
        if not sma or not klines:
            return False

        curr_price = float(klines[0][4])
        open_price = float(klines[0][1])
        if open_price == 0:
            return False  # Prevent division by zero
        change = (curr_price - open_price) / open_price * 100

        meets_conditions = change <= config["dip_threshold"] and curr_price < sma
        logger.debug(
            f"Entry check for {symbol}: change={change:.2f}%, "
            f"dip_threshold={config['dip_threshold']}, curr_price={curr_price}, "
            f"sma={sma}, meets={meets_conditions}"
        )
        return meets_conditions
    except Exception as e:
        logger.error(f"Error checking entry conditions for {symbol}: {e}")
        return False
