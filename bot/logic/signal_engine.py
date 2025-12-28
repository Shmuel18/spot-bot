import structlog
from binance import AsyncClient
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple
from decimal import Decimal

logger = structlog.get_logger(__name__)

# Cache for SMA values
sma_cache: Dict[Tuple[str, str], Tuple[Decimal, datetime]] = {}
CACHE_EXPIRY_MINUTES = 5

def parse_timeframe(timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == 'm': return value * 60
    elif unit == 'h': return value * 3600
    elif unit == 'd': return value * 86400
    else: raise ValueError(f"Unsupported timeframe: {unit}")

async def get_sma(client: AsyncClient, symbol: str, config: dict) -> Optional[Decimal]:
    """Calculate SMA with Decimal precision and Caching."""
    cache_key = (symbol, config["timeframe"])
    now = datetime.now(timezone.utc)

    if cache_key in sma_cache:
        val, ts = sma_cache[cache_key]
        if (now - ts).total_seconds() < CACHE_EXPIRY_MINUTES * 60:
            return val

    try:
        # Fetch enough candles for SMA
        klines = await client.get_historical_klines(symbol, config["timeframe"], limit=int(config["sma_length"]) + 1)
        if len(klines) < int(config["sma_length"]):
            return None

        closes = [Decimal(str(k[4])) for k in klines[:-1]]
        sma = sum(closes) / len(closes)
        
        sma_cache[cache_key] = (sma, now)
        return sma
    except Exception as e:
        logger.error("sma_calc_error", symbol=symbol, error=str(e))
        return None

async def check_entry_conditions(client: AsyncClient, symbol: str, config: dict) -> bool:
    """Check if conditions are met using Decimal math."""
    try:
        sma = await get_sma(client, symbol, config)
        klines = await client.get_historical_klines(symbol, config["timeframe"], limit=1)
        
        if not sma or not klines:
            return False

        curr_price = Decimal(str(klines[0][4]))
        open_price = Decimal(str(klines[0][1]))
        
        if open_price == 0: return False
        
        change = (curr_price - open_price) / open_price * 100
        dip_threshold = Decimal(str(config["dip_threshold"]))

        meets = change <= dip_threshold and curr_price < sma
        return meets
    except Exception as e:
        logger.error("entry_check_error", symbol=symbol, error=str(e))
        return False