import asyncio
import logging
import functools
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

def retry(max_retries=3, backoff_factor=2):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except BinanceAPIException as e:
                    if e.code in [429, -1003]: # Rate Limit
                        wait_time = backoff_factor ** (retries + 5) # המתנה ארוכה יותר
                        logger.error(f"RATE_LIMIT_HIT. Waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    elif e.code == -1001: # Disconnected
                        await asyncio.sleep(backoff_factor ** retries)
                    else:
                        raise e # שגיאות קריטיות לא מנסים שוב
                    retries += 1
                except Exception as e:
                    logger.warning(f"Connection error: {e}. Retrying...")
                    await asyncio.sleep(backoff_factor ** retries)
                    retries += 1
            return None
        return wrapper
    return decorator