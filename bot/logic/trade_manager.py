import structlog
import uuid
from decimal import Decimal, ROUND_FLOOR
from binance import AsyncClient

logger = structlog.get_logger(__name__)

async def round_to_precision(value: Decimal, step_size: str) -> Decimal:
    return value.quantize(Decimal(step_size), rounding=ROUND_FLOOR)

class TradeManager:
    def __init__(self, client: AsyncClient, config: dict):
        self.client = client
        self.config = config

    async def get_symbol_filters(self, symbol: str):
        info = await self.client.get_symbol_info(symbol)
        filters = {f['filterType']: f for f in info['filters']}
        return filters

    async def place_tp_order(self, symbol: str, qty: Decimal, avg_price: Decimal):
        try:
            filters = await self.get_symbol_filters(symbol)
            tick_size = filters['PRICE_FILTER']['tickSize']
            
            tp_price = avg_price * (1 + Decimal(str(self.config['tp_percent'])) / 100)
            rounded_tp = await round_to_precision(tp_price, tick_size)

            if self.config['dry_run']:
                return {"orderId": f"DRY_{uuid.uuid4().hex[:8]}", "price": rounded_tp}

            return await self.client.order_limit_sell(
                symbol=symbol,
                quantity=float(qty),
                price=float(rounded_tp)
            )
        except Exception as e:
            logger.error("failed_to_place_tp", symbol=symbol, error=str(e))
            return None

    async def execute_dca(self, symbol: str, current_qty: Decimal, current_avg: Decimal, old_tp_id: str):
        """
        ביצוע DCA בצורה בטוחה: קודם קנייה, אחר כך ביטול TP ישן, ואז יצירת TP חדש.
        """
        try:
            # 1. קנייה בשוק
            ticker = await self.client.get_ticker(symbol=symbol)
            curr_p = Decimal(ticker["lastPrice"])
            
            # חישוב כמות לפי ה-Scale הנוכחי (דוגמה פשוטה)
            buy_qty = current_qty * Decimal("1.0") 
            
            if not self.config['dry_run']:
                await self.client.order_market_buy(symbol=symbol, quantity=float(buy_qty))
                if old_tp_id:
                    try: await self.client.cancel_order(symbol=symbol, orderId=old_tp_id)
                    except: pass

            new_qty = current_qty + buy_qty
            new_avg = (current_avg * current_qty + curr_p * buy_qty) / new_qty
            
            new_tp = await self.place_tp_order(symbol, new_qty, new_avg)
            return {"new_avg": new_avg, "new_qty": new_qty, "tp_order": new_tp}
        except Exception as e:
            logger.error("dca_failed", symbol=symbol, error=str(e))
            return None