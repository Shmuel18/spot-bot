import structlog
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Tuple

logger = structlog.get_logger(__name__)
sma_cache: Dict[Tuple[str, str], Tuple[Decimal, datetime]] = {}

async def get_sma(client, symbol, config):
    key = (symbol, config['timeframe'])
    now = datetime.now(timezone.utc)
    
    if key in sma_cache:
        val, ts = sma_cache[key]
        if (now - ts).total_seconds() < 300: # 5 דקות Cache
            return val

    try:
        klines = await client.get_historical_klines(symbol, config['timeframe'], limit=config['sma_length'] + 1)
        if len(klines) < config['sma_length']: return None
        
        closes = [Decimal(k[4]) for k in klines[:-1]]
        sma = sum(closes) / len(closes)
        sma_cache[key] = (sma, now)
        return sma
    except Exception as e:
        logger.error("sma_error", symbol=symbol, error=str(e))
        return None