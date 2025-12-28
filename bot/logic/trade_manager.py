import structlog
import uuid
from decimal import Decimal, ROUND_FLOOR
from binance import AsyncClient

logger = structlog.get_logger(__name__)

async def round_to_precision(value: Decimal, step_size: str) -> Decimal:
    """Helper for precision rounding."""
    return value.quantize(Decimal(str(step_size)), rounding=ROUND_FLOOR)

async def get_total_balance(client: AsyncClient, config: dict, open_trades: dict) -> Decimal:
    """Calculate NLV using Decimal."""
    try:
        account = await client.get_account()
        total_nlv = Decimal('0')
        
        usdt_data = next((b for b in account["balances"] if b["asset"] == "USDT"), None)
        if usdt_data:
            total_nlv += Decimal(str(usdt_data["free"])) + Decimal(str(usdt_data["locked"]))
            
        if open_trades:
            tickers = await client.get_ticker()
            ticker_dict = {t["symbol"]: Decimal(str(t["lastPrice"])) for t in tickers}
            for symbol, details in open_trades.items():
                price = ticker_dict.get(symbol, Decimal('0'))
                total_nlv += Decimal(str(details["quantity"])) * price
        return total_nlv
    except Exception as e:
        logger.error("balance_calc_error", error=str(e))
        return Decimal('0')

class TradeManager:
    def __init__(self, client: AsyncClient, config: dict):
        self.client = client
        self.config = config

    async def get_filters(self, symbol: str):
        s_info = await self.client.get_symbol_info(symbol)
        return {f["filterType"]: f for f in s_info.get("filters", [])}

    async def open_trade(self, symbol: str):
        try:
            filters = await self.get_filters(symbol)
            lot_size = filters["LOT_SIZE"]["stepSize"]
            
            ticker = await self.client.get_ticker(symbol=symbol)
            curr_price = Decimal(str(ticker["lastPrice"]))

            account = await client.get_account()
            usdt_free = Decimal(next((b["free"] for b in account["balances"] if b["asset"] == "USDT"), "0"))
            
            pos_size_usdt = usdt_free * (Decimal(str(self.config["position_size_percent"])) / 100)
            qty = await round_to_precision(pos_size_usdt / curr_price, lot_size)

            if qty <= 0: return None
            
            if self.config["dry_run"]:
                return {"quantity": qty, "avg_price": curr_price}

            order = await self.client.order_market_buy(symbol=symbol, quantity=float(qty))
            return {"quantity": qty, "avg_price": curr_price, "order": order}
        except Exception as e:
            logger.error("open_trade_error", symbol=symbol, error=str(e))
            return None

    async def place_tp_order(self, symbol: str, quantity: Decimal, avg_price: Decimal):
        try:
            filters = await self.get_filters(symbol)
            tick_size = filters["PRICE_FILTER"]["tickSize"]
            tp_price = await round_to_precision(avg_price * (1 + Decimal(str(self.config["tp_percent"])) / 100), tick_size)

            if self.config["dry_run"]:
                return {"orderId": "DRY_TP", "price": tp_price}

            return await self.client.order_limit_sell(symbol=symbol, quantity=float(quantity), price=float(tp_price))
        except Exception as e:
            logger.error("tp_error", symbol=symbol, error=str(e))
            return None