import structlog
from decimal import Decimal

logger = structlog.get_logger(__name__)

async def check_dca_conditions(client, symbol: str, config: dict, current_avg_price: Decimal) -> bool:
    try:
        ticker = await client.get_ticker(symbol=symbol)
        current_price = Decimal(str(ticker["lastPrice"]))

        # חישוב אחוז ירידה בצורה מדויקת
        price_drop = ((current_avg_price - current_price) / current_avg_price) * 100
        dca_trigger = Decimal(str(config["dca_trigger"]))

        if price_drop >= dca_trigger:
            logger.info("dca_triggered", symbol=symbol, drop=f"{price_drop:.2f}%")
            return True
        return False

    except Exception as e:
        logger.error("dca_check_error", symbol=symbol, error=str(e))
        return False