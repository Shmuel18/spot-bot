import structlog
from decimal import Decimal, ROUND_FLOOR
from bot.database.database_service import TradeRepository

logger = structlog.get_logger(__name__)

def round_to_precision(value: Decimal, step_size: str) -> Decimal:
    """מעגל ערך לדיוק הנדרש על ידי הבורסה באמצעות Decimal בלבד."""
    return value.quantize(Decimal(str(step_size)), rounding=ROUND_FLOOR)

async def get_total_balance(client, config: dict, open_trades: list) -> Decimal:
    """חישוב השווי הכולל של החשבון (NLV) בדיוק מקסימלי."""
    try:
        account = await client.get_account()
        total_nlv = Decimal('0')
        
        # יתרה פנויה ב-USDT
        usdt_data = next((b for b in account["balances"] if b["asset"] == "USDT"), None)
        if usdt_data:
            total_nlv += Decimal(str(usdt_data["free"])) + Decimal(str(usdt_data["locked"]))
            
        # הוספת שווי הפוזיציות הפתוחות
        if open_trades:
            tickers = await client.get_ticker()
            # יצירת מילון מחירים מבוסס Decimal
            ticker_dict = {t["symbol"]: Decimal(str(t["lastPrice"])) for t in tickers}
            for trade in open_trades:
                symbol = trade["symbol"]
                price = ticker_dict.get(symbol, Decimal('0'))
                total_nlv += Decimal(str(trade["base_qty"])) * price
        return total_nlv
    except Exception as e:
        logger.error("balance_calc_error", error=str(e))
        return Decimal('0')

class TradeManager:
    def __init__(self, client, config: dict):
        self.client = client
        self.config = config

    async def _get_precision_tools(self, symbol: str):
        s_info = await self.client.get_symbol_info(symbol)
        filters = {f["filterType"]: f for f in s_info.get("filters", [])}
        return (
            filters["LOT_SIZE"]["stepSize"],
            filters["PRICE_FILTER"]["tickSize"]
        )

    async def open_trade(self, symbol: str):
        trade_id = await TradeRepository.create_pending_trade(symbol)
        try:
            step_size, tick_size = await self._get_precision_tools(symbol)
            ticker = await self.client.get_ticker(symbol=symbol)
            curr_price = Decimal(str(ticker["lastPrice"]))

            account = await self.client.get_account()
            usdt_free = Decimal(next((b["free"] for b in account["balances"] if b["asset"] == "USDT"), "0"))
            
            pos_size_usdt = usdt_free * (Decimal(str(self.config["position_size_percent"])) / 100)
            qty = round_to_precision(pos_size_usdt / curr_price, step_size)

            if qty <= 0:
                await TradeRepository.close_trade(trade_id, "FAILED_INSUFFICIENT_FUNDS")
                return None

            if not self.config["dry_run"]:
                await self.client.order_market_buy(symbol=symbol, quantity=float(qty))
                tp_order = await self.place_tp_order(symbol, qty, curr_price)
                tp_id = tp_order["orderId"] if tp_order else "MANUAL_REQUIRED"
            else:
                tp_id = "DRY_RUN_TP"

            await TradeRepository.confirm_trade(trade_id, curr_price, qty, tp_id)
            return True
        except Exception as e:
            logger.error("critical_trade_error", symbol=symbol, error=str(e))
            raise

    async def place_tp_order(self, symbol: str, quantity: Decimal, avg_price: Decimal):
        _, tick_size = await self._get_precision_tools(symbol)
        tp_price = round_to_precision(avg_price * (1 + Decimal(str(self.config["tp_percent"])) / 100), tick_size)
        if self.config["dry_run"]: return {"orderId": "DRY_TP"}
        return await self.client.order_limit_sell(symbol=symbol, quantity=float(quantity), price=str(tp_price))