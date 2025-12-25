import asyncio
import logging
import math
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from bot.database.database_service import insert_order, update_trade_tp_order_id
from bot.utils.retry import retry

logger = logging.getLogger(__name__)

def find_filter(symbol_info: dict, filter_type: str) -> dict | None:
    for f in symbol_info.get('filters', []):
        if f['filterType'] == filter_type:
            return f
    return None

async def round_quantity(quantity: float, step_size: str) -> float:
    precision = int(round(-math.log10(float(step_size))))
    # עיגול כלפי מטה (Floor) למניעת שגיאת יתרה חסרה
    return math.floor(quantity * 10**precision) / 10**precision

async def round_price(price: float, tick_size: str) -> float:
    precision = int(round(-math.log10(float(tick_size))))
    return math.floor(price * 10**precision) / 10**precision

@retry(max_retries=3, backoff_factor=2)
async def get_total_balance(client: AsyncClient, config: dict, open_trades: dict) -> float:
    try:
        account = await client.get_account()
        balances = account['balances']
        total_balance = 0.0
        
        # 1. חישוב יתרות בארנק
        for b in balances:
            asset = b['asset']
            amount = float(b['free']) + float(b['locked'])
            if amount <= 0: continue
            
            if asset == 'USDT':
                total_balance += amount
            elif asset in config.get('balance_assets', []):
                try:
                    ticker = await client.get_ticker(symbol=asset + 'USDT')
                    total_balance += amount * float(ticker['lastPrice'])
                except: continue

        # 2. הוספת PnL לא ממומש מעסקאות פתוחות
        if open_trades:
            ticker_stats = await client.get_ticker(symbols=list(open_trades.keys()))
            prices = {item['symbol']: float(item['lastPrice']) for item in ticker_stats}
            
            for symbol, details in open_trades.items():
                current_price = prices.get(symbol, 0)
                if current_price > 0:
                    unrealized_pnl = (current_price - details['avg_price']) * details['quantity']
                    total_balance += unrealized_pnl

        return total_balance
    except Exception as e:
        logger.error(f"Error calculating total balance: {e}")
        return 0.0

@retry(max_retries=3, backoff_factor=2)
async def open_trade(client: AsyncClient, symbol: str, config: dict) -> dict | None:
    try:
        s_info = await client.get_symbol_info(symbol)
        lot_filter = find_filter(s_info, 'LOT_SIZE')
        
        # חישוב כמות לפי אחוז מהיתרה הפנויה
        account = await client.get_account()
        usdt_free = next((float(b['free']) for b in account['balances'] if b['asset'] == 'USDT'), 0.0)
        quantity = (usdt_free * (config['position_size_percent'] / 100))
        quantity = await round_quantity(quantity / float((await client.get_ticker(symbol=symbol))['lastPrice']), lot_filter['stepSize'])

        if config['dry_run']:
            logger.info(f"DRY RUN: Buy {symbol}")
            ticker = await client.get_ticker(symbol=symbol)
            return {"order": {"orderId": "DRY_ID"}, "quantity": quantity, "avg_price": float(ticker['lastPrice'])}
        
        order = await client.order_market_buy(symbol=symbol, quantity=quantity)
        ticker = await client.get_ticker(symbol=symbol)
        return {"order": order, "quantity": quantity, "avg_price": float(ticker['lastPrice'])}
    except Exception as e:
        logger.error(f"Open trade error {symbol}: {e}")
        return None

@retry(max_retries=3, backoff_factor=2)
async def place_take_profit_order(client: AsyncClient, symbol: str, quantity: float, avg_price: float, config: dict) -> dict | None:
    try:
        s_info = await client.get_symbol_info(symbol)
        tick_filter = find_filter(s_info, 'PRICE_FILTER')
        tp_price = await round_price(avg_price * (1 + (config['tp_percent'] / 100)), tick_filter['tickSize'])

        if config['dry_run']:
            return {"orderId": "DRY_TP_ID", "status": "FILLED", "price": tp_price, "origQty": quantity}
        
        return await client.order_limit_sell(symbol=symbol, quantity=quantity, price=tp_price)
    except Exception as e:
        logger.error(f"TP order error {symbol}: {e}")
        return None

@retry(max_retries=3, backoff_factor=2)
async def dca(client: AsyncClient, symbol: str, config: dict, current_qty: float, current_avg: float, trade_id: int, tp_id: str, count: int) -> dict | None:
    try:
        if not config['dry_run']:
            await client.cancel_order(symbol=symbol, orderId=tp_id)
        
        s_info = await client.get_symbol_info(symbol)
        lot_filter = find_filter(s_info, 'LOT_SIZE')
        
        scale = config['dca_scales'][count] if count < len(config['dca_scales']) else config['dca_scales'][-1]
        dca_qty = await round_quantity(current_qty * scale, lot_filter['stepSize'])
        
        if config['dry_run']:
            dca_order = {"orderId": "DRY_DCA_ID"}
        else:
            dca_order = await client.order_market_buy(symbol=symbol, quantity=dca_qty)
            
        ticker = await client.get_ticker(symbol=symbol)
        curr_p = float(ticker['lastPrice'])
        new_qty = current_qty + dca_qty
        new_avg = (current_avg * current_qty + curr_p * dca_qty) / new_qty
        
        tp_order = await place_take_profit_order(client, symbol, new_qty, new_avg, config)
        return {"tp_order": tp_order, "new_avg_price": new_avg, "new_quantity": new_qty}
    except Exception as e:
        logger.error(f"DCA error {symbol}: {e}")
        return None