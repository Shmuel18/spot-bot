import logging
import math
from binance import AsyncClient
from bot.utils.retry import retry

logger = logging.getLogger(__name__)


def find_filter(symbol_info, filter_type):
    for f in symbol_info.get("filters", []):
        if f["filterType"] == filter_type:
            return f
    return None


async def round_quantity(quantity, step_size):
    precision = int(round(-math.log10(float(step_size))))
    return math.floor(quantity * 10**precision) / 10**precision


async def round_price(price, tick_size):
    precision = int(round(-math.log10(float(tick_size))))
    return math.floor(price * 10**precision) / 10**precision


@retry(max_retries=3)
async def get_total_balance(client: AsyncClient, config: dict, open_trades: dict) -> float:
    try:
        account = await client.get_account()
        total_nlv = 0.0

        # 1. USDT balance
        total_nlv += next(
            (float(b["free"]) + float(b["locked"]) for b in account["balances"] if b["asset"] == "USDT"), 0.0
        )

        # 2. Market value of open positions
        if open_trades:
            symbols = list(open_trades.keys())
            tickers = await client.get_ticker(symbols=symbols)
            ticker_dict = {t["symbol"]: float(t["lastPrice"]) for t in tickers}
            for symbol, details in open_trades.items():
                total_nlv += details["quantity"] * ticker_dict.get(symbol, 0.0)

        return total_nlv
    except Exception as e:
        logger.error(f"Balance calculation error: {e}")
        return 0.0


@retry(max_retries=3)
async def open_trade(client: AsyncClient, symbol: str, config: dict):
    try:
        s_info = await client.get_symbol_info(symbol)
        lot_size = find_filter(s_info, "LOT_SIZE")

        ticker = await client.get_ticker(symbol=symbol)
        curr_price = float(ticker["lastPrice"])

        usdt_balance = next(
            (float(b["free"]) for b in (await client.get_account())["balances"] if b["asset"] == "USDT"), 0.0
        )
        qty = await round_quantity(
            (usdt_balance * (config["position_size_percent"] / 100)) / curr_price, lot_size["stepSize"]
        )

        if config["dry_run"]:
            return {"quantity": qty, "avg_price": curr_price}

        order = await client.order_market_buy(symbol=symbol, quantity=qty)
        return {"quantity": qty, "avg_price": curr_price, "order": order}
    except Exception as e:
        logger.error(f"Open trade error: {e}")
        return None


@retry(max_retries=3)
async def place_take_profit_order(client, symbol, quantity, avg_price, config):
    try:
        s_info = await client.get_symbol_info(symbol)
        tick_size = find_filter(s_info, "PRICE_FILTER")["tickSize"]
        tp_price = await round_price(avg_price * (1 + config["tp_percent"] / 100), tick_size)

        if config["dry_run"]:
            return {"orderId": "DRY_TP", "status": "NEW", "price": tp_price, "origQty": quantity}

        return await client.order_limit_sell(symbol=symbol, quantity=quantity, price=tp_price)
    except Exception as e:
        logger.error(f"TP placement error: {e}")
        return None


@retry(max_retries=3)
async def dca(client, symbol, config, current_qty, current_avg, trade_id, tp_id, count):
    try:
        if not config["dry_run"]:
            await client.cancel_order(symbol=symbol, orderId=tp_id)

        s_info = await client.get_symbol_info(symbol)
        lot_size = find_filter(s_info, "LOT_SIZE")["stepSize"]

        scale = config["dca_scales"][min(count, len(config["dca_scales"]) - 1)]
        dca_qty = await round_quantity(current_qty * scale, lot_size)

        ticker = await client.get_ticker(symbol=symbol)
        curr_p = float(ticker["lastPrice"])

        if not config["dry_run"]:
            await client.order_market_buy(symbol=symbol, quantity=dca_qty)

        new_qty = current_qty + dca_qty
        new_avg = (current_avg * current_qty + curr_p * dca_qty) / new_qty
        tp_order = await place_take_profit_order(client, symbol, new_qty, new_avg, config)

        return {"tp_order": tp_order, "new_avg_price": new_avg, "new_quantity": new_qty}
    except Exception as e:
        logger.error(f"DCA execution error: {e}")
        return None
