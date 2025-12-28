import structlog
from binance import AsyncClient

logger = structlog.get_logger(__name__)


async def check_dca_conditions(client: AsyncClient, symbol: str, config: dict, current_avg_price: float):
    """
    Checks the DCA conditions for a given symbol.
    """
    try:
        # Get the current price
        ticker = await client.get_ticker(symbol=symbol)
        current_price = float(ticker["lastPrice"])

        # Calculate the price drop from the average price
        price_drop = (current_avg_price - current_price) / current_avg_price * 100

        # Check if the price drop is greater than the DCA trigger
        dca_trigger = config["dca_trigger"]
        if price_drop >= dca_trigger:
            logger.info(f"DCA conditions met for {symbol}: price_drop={price_drop}, dca_trigger={dca_trigger}")
            return True
        else:
            logger.debug(f"DCA conditions not met for {symbol}: price_drop={price_drop}, dca_trigger={dca_trigger}")
            return False

    except Exception as e:
        logger.error(f"Error checking DCA conditions for {symbol}: {e}")
        return False
