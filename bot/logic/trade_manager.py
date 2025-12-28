import structlog
import uuid
from decimal import Decimal, ROUND_FLOOR, ROUND_DOWN
from binance import AsyncClient
from bot.utils.retry import retry

logger = structlog.get_logger(__name__)

def find_filter(symbol_info, filter_type):
    for f in symbol_info.get("filters", []):
        if f["filterType"] == filter_type:
            return f
    return None

async def round_step_size(quantity: Decimal, step_size: str) -> Decimal:
    step = Decimal(step_size)
    return quantity.quantize(step, rounding=ROUND_FLOOR)

async def round_tick_size(price: Decimal, tick_size: str) -> Decimal:
    tick = Decimal(tick_size)
    return price.quantize(tick, rounding=ROUND_FLOOR)

@retry(max_retries=3)
async def get_total_balance(client: AsyncClient, config: dict, open_trades: dict) -> Decimal:
    try:
        account = await client.get_account()
        total_nlv = Decimal('0')

        # 1. USDT balance
        usdt_data = next((b for b in account["balances"] if b["asset"] == "USDT"), None)
        if usdt_data:
            total_nlv += Decimal(usdt_data["free"]) + Decimal(usdt_data["locked"])

        # 2. Market value of open positions
        if open_trades:
            # משתמשים בטיקר אחד כדי לחסוך קריאות
            tickers = await client.get_ticker()
            ticker_dict = {t["symbol"]: Decimal(t["lastPrice"]) for t in tickers}
            for symbol, details in open_trades.items():
                price = ticker_dict.get(symbol, Decimal('0'))
                total_nlv += Decimal(str(details["quantity"])) * price

        return total_nlv
    except Exception as e:
        logger.error(f"Balance calculation error: {e}")
        return Decimal('0')

@retry(max_retries=3)
async def open_trade(client: AsyncClient, symbol: str, config: dict):
    try:
        s_info = await client.get_symbol_info(symbol)
        lot_size = find_filter(s_info, "LOT_SIZE")["stepSize"]

        ticker = await client.get_ticker(symbol=symbol)
        curr_price = Decimal(ticker["lastPrice"])

        account = await client.get_account()
        usdt_free = Decimal(next((b["free"] for b in account["balances"] if b["asset"] == "USDT"), "0"))
        
        pos_size_usdt = usdt_free * (Decimal(str(config["position_size_percent"])) / 100)
        qty = await round_step_size(pos_size_usdt / curr_price, lot_size)

        if qty <= 0:
            logger.warning(f"Quantity too low for {symbol}")
            return None

        if config["dry_run"]:
            return {"quantity": qty, "avg_price": curr_price}

        client_order_id = f"open_{symbol}_{uuid.uuid4().hex[:16]}"
        order = await client.order_market_buy(symbol=symbol, quantity=float(qty), newClientOrderId=client_order_id)
        return {"quantity": qty, "avg_price": curr_price, "order": order}
    except Exception as e:
        logger.error(f"Open trade error: {e}")
        return None

@retry(max_retries=3)
async def place_take_profit_order(client, symbol, quantity: Decimal, avg_price: Decimal, config):
    try:
        s_info = await client.get_symbol_info(symbol)
        tick_size = find_filter(s_info, "PRICE_FILTER")["tickSize"]
        tp_percent = Decimal(str(config["tp_percent"])) / 100
        tp_price = await round_tick_size(avg_price * (1 + tp_percent), tick_size)

        if config["dry_run"]:
            return {"orderId": "DRY_TP", "status": "NEW", "price": tp_price, "origQty": quantity}

        client_order_id = f"tp_{symbol}_{uuid.uuid4().hex[:16]}"
        return await client.order_limit_sell(
            symbol=symbol, 
            quantity=float(quantity), 
            price=float(tp_price), 
            newClientOrderId=client_order_id
        )
    except Exception as e:
        logger.error(f"TP placement error: {e}")
        return None

@retry(max_retries=3)
async def dca(client, symbol, config, current_qty: Decimal, current_avg: Decimal, trade_id, tp_id, count):
    try:
        # Cancel previous TP
        if not config["dry_run"] and tp_id:
            try: await client.cancel_order(symbol=symbol, orderId=tp_id)
            except: pass

        s_info = await client.get_symbol_info(symbol)
        lot_size = find_filter(s_info, "LOT_SIZE")["stepSize"]

        scale = Decimal(str(config["dca_scales"][min(count, len(config["dca_scales"]) - 1)]))
        # גודל ה-DCA הוא מכפלה של הכמות ההתחלתית
        dca_qty = await round_step_size(current_qty * scale, lot_size)

        ticker = await client.get_ticker(symbol=symbol)
        curr_p = Decimal(ticker["lastPrice"])

        if not config["dry_run"]:
            await client.order_market_buy(symbol=symbol, quantity=float(dca_qty))

        new_qty = current_qty + dca_qty
        new_avg = (current_avg * current_qty + curr_p * dca_qty) / new_qty
        tp_order = await place_take_profit_order(client, symbol, new_qty, new_avg, config)

        return {"tp_order": tp_order, "new_avg_price": new_avg, "new_quantity": new_qty}
    except Exception as e:
        logger.error(f"DCA execution error: {e}")
        return None