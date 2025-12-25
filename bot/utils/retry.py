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
                    if e.code == -1001:  # Disconnected
                        logger.warning(f"Binance API Disconnected. Retrying in {backoff_factor ** retries} seconds...")
                        await asyncio.sleep(backoff_factor ** retries)
                    elif e.code == 429 or e.code == -1003: # Rate limit error codes
                        logger.warning(f"Rate limit exceeded. Retrying in {backoff_factor ** retries} seconds...")
                        await asyncio.sleep(backoff_factor ** retries)
                    elif e.code == -2015: # Invalid API-key, IP, or permissions for action.
                        logger.error(f"Invalid API-key, IP, or permissions for action. Stopping retries.")
                        raise
                    else:
                        logger.exception(f"Exception occurred. Retrying in {backoff_factor ** retries} seconds...")
                        await asyncio.sleep(backoff_factor ** retries)

                    retries += 1
                except Exception as e:
                    logger.exception(f"Exception occurred. Retrying in {backoff_factor ** retries} seconds...")
                    await asyncio.sleep(backoff_factor ** retries)
                    retries += 1
            logger.error(f"Max retries exceeded for function {func.__name__}")
            return None
        return wrapper
    return decorator