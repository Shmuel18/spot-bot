import time
import math
import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException

# === הגדרות API ===
API_KEY = "GCcsH63yd9oyw5ZhnL7DhtCUBw87sngF8dEt6aZH3fXHd3fnw5JeIba1IfT5ZyID"
API_SECRET = "e8BVesKVV7r5UvdwwpE8oH9dABOXry2aX6PdOuzcuACR6Va0YDiszE4aGm44mLnS"
client = Client(API_KEY, API_SECRET)

# === פרמטרים כלליים ===
DROP_TRIGGER = 3         # אחוז ירידה בנר 15 דקות לכניסה ל-LONG
RISE_TRIGGER = 3         # אחוז עלייה בנר 15 דקות לכניסה ל-SHORT
LONG_SIZE = 0.001        # אחוז מהתיק לכל עסקה
LEVERAGE = 8             # מינוף
TAKE_PROFIT = 0.05       # TP ברווח 3%
SCAN_INTERVAL = 30       # סריקה כל 10 שניות
MAX_WORKERS = 5         # מספר סימבולים במקביל

# --- דגלים שניתן להתאים ---
ENABLE_MONITOR = True            # הדלק/כבה את המנגנון שבודק TP ומבצע מיצוע
ALLOW_AVERAGING = True           # אפשר/לאפשר מיצוע (Averaging)
ENTER_ON_BOTH_TRIGGERS = True   # כניסה לשני הצדדים באותו טריגר

# --- פרמטרים למיצוע ---
AVERAGING_THRESHOLD_LONG = 40   # אחוז הפסד ללונג לפני מיצוע
AVERAGING_THRESHOLD_SHORT = 500  # אחוז הפסד לשורט לפני מיצוע
AVERAGING_MULTIPLIER = 2        # פי כמה מהמארג'ין להשתמש למיצוע
MAX_AVERAGES_PER_POSITION = 4   # מספר מקסימום מיצועים לפוזיציה

# --- הגבלות חדשות ---
MAX_LONG_TRADES = 40     # מקסימום עסקאות LONG במקביל (0 = חסימה)
MAX_SHORT_TRADES = 0    # מקסימום עסקאות SHORT במקביל (0 = חסימה)

handled_candles = {}     # נרות שכבר טופלו
averaging_counts = defaultdict(lambda: {"LONG": 0, "SHORT": 0})  # ספירת מיצועים

# === לוגים ===
logging.basicConfig(
    filename="trading_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

# === נעילות per-symbol למניעת race conditions ===
symbol_locks = defaultdict(threading.Lock)

# --- פונקציות עזר ---

def get_futures_symbols():
    info = client.futures_exchange_info()
    return {s['symbol']: s for s in info['symbols'] if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING'}

def get_open_positions():
    try:
        positions = client.futures_position_information()
        open_positions = {}
        for pos in positions:
            amt = float(pos['positionAmt'])
            side = pos['positionSide']
            sym = pos['symbol']
            if amt != 0:
                if sym not in open_positions:
                    open_positions[sym] = {"LONG": 0, "SHORT": 0}
                open_positions[sym][side] = amt
        return open_positions
    except Exception as e:
        logging.error(f"שגיאה בשליפת פוזיציות: {e}")
        return {}

def cancel_orders_for_symbol(symbol, position_side=None):
    try:
        open_orders = client.futures_get_open_orders(symbol=symbol)
        to_cancel = []
        for order in open_orders:
            order_pos_side = order.get('positionSide')
            if position_side is None or order_pos_side == position_side:
                to_cancel.append(order)
        for order in to_cancel:
            try:
                client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
            except Exception as e:
                logging.warning(f"שגיאה בביטול הזמנה {order.get('orderId')} של {symbol}: {e}")
        if to_cancel:
            print(f"🗑️ נמחקו {len(to_cancel)} הזמנות של {symbol} (position_side={position_side})")
    except Exception as e:
        logging.warning(f"שגיאה בביטול הזמנות ב-{symbol}: {e}")

def calc_amount(balance, entry_price, symbol_info):
    amount = (balance * LONG_SIZE * LEVERAGE) / entry_price
    step_size, min_qty, precision = None, None, 3
    for f in symbol_info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = float(f['stepSize'])
            min_qty = float(f['minQty'])
        if f['filterType'] == 'PRICE_FILTER':
            precision = symbol_info.get('quantityPrecision', 3)
    if step_size:
        amount = math.floor(amount / step_size) * step_size
    if min_qty and amount < min_qty:
        return None
    return round(amount, precision)

def get_tick_size(symbol_info):
    for f in symbol_info['filters']:
        if f['filterType'] == 'PRICE_FILTER':
            return float(f.get('tickSize', 0))
    return None

def round_price_by_tick(price, tick):
    if not tick or tick == 0:
        return price
    return math.floor(price / tick) * tick

# --- פונקציה חדשה: חישוב SMA ---
def get_sma(symbol, length=150):
    try:
        klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=length)
        closes = [float(k[4]) for k in klines]
        if len(closes) < length:
            return None
        return sum(closes) / len(closes)
    except Exception as e:
        logging.error(f"שגיאה בחישוב SMA ל-{symbol}: {e}")
        return None

def open_position(symbol, entry_price, symbol_info, side, position_side):
    lock = symbol_locks[symbol]
    with lock:
        balances = client.futures_account_balance()
        balance = next((float(b['balance']) for b in balances if b['asset'] == 'USDT'), 0)
        if balance <= 0:
            print(f"אין יתרה ב-{symbol}, מדלג...")
            return False

        amount = calc_amount(balance, entry_price, symbol_info)
        if not amount or amount <= 0:
            print(f"עסקה קטנה מדי ב-{symbol}, מדלג...")
            return False

        try:
            cancel_orders_for_symbol(symbol, position_side=position_side)

            try:
                client.futures_change_margin_type(symbol=symbol, marginType="CROSSED")
            except BinanceAPIException as e:
                if "No need to change margin type" not in str(e):
                    raise

            client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)

            order_resp = client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=amount,
                positionSide=position_side
            )
            print(f"✅ נכנס {position_side} על {symbol}, כמות {amount}, בקשת כניסה נשלחה. ניסיון לקבוע TP...")
            logging.info(f"{symbol} {position_side} market order response: {order_resp}")

            entry_price_real = None
            attempts = 0
            while attempts < 6 and entry_price_real is None:
                try:
                    positions = client.futures_position_information(symbol=symbol)
                    for p in positions:
                        if p.get('positionSide') == position_side:
                            amt = float(p.get('positionAmt', 0))
                            if amt != 0:
                                ep = float(p.get('entryPrice', 0))
                                if ep and ep != 0.0:
                                    entry_price_real = ep
                                    break
                    if entry_price_real is None:
                        attempts += 1
                        time.sleep(1)
                except Exception as e:
                    logging.warning(f"כשל בקריאת פוזיציה לקבלת entryPrice עבור {symbol}: {e}")
                    attempts += 1
                    time.sleep(1)

            if entry_price_real is None:
                logging.warning(f"לא נמצא entryPrice אמיתי עבור {symbol}, משתמשים ב-entry_price המשוער {entry_price}")
                entry_price_real = entry_price

            tick = get_tick_size(symbol_info)
            tp_multiplier = (1 + TAKE_PROFIT) if position_side == 'LONG' else (1 - TAKE_PROFIT)
            raw_tp = entry_price_real * tp_multiplier
            tp_price = round_price_by_tick(raw_tp, tick)
            if tick and tick > 0:
                if position_side == 'LONG':
                    if tp_price < raw_tp:
                        tp_price = tp_price + tick
                else:
                    if tp_price > raw_tp:
                        tp_price = tp_price - tick
            if tp_price <= 0:
                tp_price = round_price_by_tick(raw_tp, tick) if tick else raw_tp
            try:
                tp_price = float(round(tp_price, 8))
            except:
                tp_price = float(tp_price)

            try:
                tp_order = client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_SELL if position_side == 'LONG' else SIDE_BUY,
                    type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                    stopPrice=tp_price,
                    closePosition=True,
                    positionSide=position_side,
                    workingType='MARK_PRICE'
                )
                print(f"🎯 TP Market הוגדר על {tp_price} ({position_side}) — entry real: {entry_price_real}")
                logging.info(f"{symbol} {position_side} נפתח עם TP {tp_price}, entry_real={entry_price_real}, tp_resp={tp_order}")
            except BinanceAPIException as e:
                logging.error(f"BinanceAPIException ביצירת TP ל-{symbol}: {e}")
                print(f"שגיאת Binance ביצירת TP ל-{symbol}: {e}")
                if tick and tick > 0:
                    try:
                        alt_tp = tp_price + (tick if position_side == 'LONG' else -tick)
                        tp_order = client.futures_create_order(
                            symbol=symbol,
                            side=SIDE_SELL if position_side == 'LONG' else SIDE_BUY,
                            type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                            stopPrice=alt_tp,
                            closePosition=True,
                            positionSide=position_side,
                            workingType='MARK_PRICE'
                        )
                        print(f"🎯 ניסיון חלופי — TP הוגדר על {alt_tp} ({position_side})")
                        logging.info(f"{symbol} {position_side} TP חלופי הוגדר על {alt_tp}, tp_resp={tp_order}")
                    except Exception as e2:
                        logging.error(f"כשל גם בניסיון החלופי להגדרת TP עבור {symbol}: {e2}")
                        print(f"כשל גם בניסיון חלופי להגדרת TP עבור {symbol}: {e2}")
                return True
            return True

        except BinanceAPIException as e:
            print(f"שגיאת Binance בפתיחת {position_side} על {symbol}: {e.message}")
            logging.error(f"BinanceAPIException: {e}")
            return False
        except Exception as e:
            print(f"שגיאה כללית בפתיחת {position_side} על {symbol}: {e}")
            logging.error(f"Exception: {e}")
            return False

def check_symbol(symbol, symbol_info):
    try:
        klines = client.futures_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=1)
        open_price = float(klines[-1][1])
        close_price = float(klines[-1][4])
        kline_time = klines[-1][0]
        change = (close_price - open_price) / open_price * 100
        return symbol, change, open_price, close_price, kline_time
    except BinanceAPIException as e:
        logging.error(f"שגיאת Binance ב-{symbol}: {e.message}")
        return symbol, None, None, None, None
    except Exception as e:
        logging.error(f"שגיאה כללית ב-{symbol}: {e}")
        return symbol, None, None, None, None

def ensure_hedge_mode():
    try:
        info = client.futures_get_position_mode()
        if not info["dualSidePosition"]:
            print("⚠️ החשבון מוגדר על One-Way Mode, משנה ל-Hedge Mode...")
            client.futures_change_position_mode(dualSidePosition=True)
            print("✅ Hedge Mode הופעל בהצלחה")
        else:
            print("✅ Hedge Mode כבר פעיל")
    except Exception as e:
        logging.error(f"שגיאה בווידוא Hedge Mode: {e}")
        print(f"שגיאה בווידוא Hedge Mode: {e}")
def monitor_positions(symbols_info):
    try:
        positions = client.futures_position_information()
        for pos in positions:
            sym = pos['symbol']
            amt = float(pos['positionAmt'])
            if amt == 0:
                continue
            if sym not in symbols_info:
                continue

            lock = symbol_locks[sym]
            with lock:
                entry_price = float(pos.get('entryPrice', 0) or 0)
                position_side = pos.get('positionSide')
                mark_price = float(pos.get('markPrice', 0) or 0)
                if mark_price == 0:
                    try:
                        t = client.futures_mark_price(symbol=sym)
                        mark_price = float(t.get('markPrice', 0) or 0)
                    except:
                        mark_price = 0

                if entry_price == 0 or mark_price == 0:
                    continue

                tp_multiplier = (1 + TAKE_PROFIT) if position_side == 'LONG' else (1 - TAKE_PROFIT)
                raw_tp = entry_price * tp_multiplier

                # --- בדיקת TP ---
                if (position_side == 'LONG' and mark_price >= raw_tp) or \
                   (position_side == 'SHORT' and mark_price <= raw_tp):
                    print(f"🎯 {sym} עבר TP (mark={mark_price}, tp={raw_tp}), סוגר ({position_side})...")
                    try:
                        client.futures_create_order(
                            symbol=sym,
                            side=SIDE_SELL if position_side == 'LONG' else SIDE_BUY,
                            type=ORDER_TYPE_MARKET,
                            quantity=abs(amt),
                            positionSide=position_side
                        )
                        logging.info(f"Closed {sym} {position_side} due to TP reached (mark={mark_price}, tp={raw_tp})")
                    except Exception as e:
                        logging.error(f"כשל בסגירת {sym} לאחר שנכנס ל-TP: {e}")
                    continue

                # --- בדיקה אם יש TP פתוח ---
                try:
                    orders = client.futures_get_open_orders(symbol=sym)
                except Exception as e:
                    orders = []
                    logging.warning(f"כשל בשליפת הזמנות פתוחות ל-{sym}: {e}")

                has_tp = any(
                    (o.get('type') == 'TAKE_PROFIT_MARKET' or o.get('type') == FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET)
                    and o.get('positionSide') == position_side
                    for o in orders
                )

                if not has_tp:
                    print(f"⚠️ אין TP פתוח ל-{sym} ({position_side}), מייצר חדש...")
                    tick = get_tick_size(symbols_info[sym])
                    tp_price = round_price_by_tick(raw_tp, tick)
                    if tick and tick > 0:
                        if position_side == 'LONG' and tp_price < raw_tp:
                            tp_price += tick
                        if position_side == 'SHORT' and tp_price > raw_tp:
                            tp_price -= tick
                    if tp_price <= 0:
                        tp_price = raw_tp
                    try:
                        client.futures_create_order(
                            symbol=sym,
                            side=SIDE_SELL if position_side == 'LONG' else SIDE_BUY,
                            type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                            stopPrice=float(round(tp_price, 8)),
                            closePosition=True,
                            positionSide=position_side,
                            workingType='MARK_PRICE'
                        )
                        logging.info(f"Created TP for {sym} {position_side} at {tp_price}")
                    except Exception as e:
                        logging.error(f"כשל ביצירת TP ל-{sym}: {e}")

                # ---------------------------
                # מיצוע עם DEBUG
                # ---------------------------
                if ALLOW_AVERAGING:
                    pnl_pct = (mark_price - entry_price) / entry_price * 100 if position_side == 'LONG' else (entry_price - mark_price) / entry_price * 100
                    threshold = AVERAGING_THRESHOLD_LONG if position_side == 'LONG' else AVERAGING_THRESHOLD_SHORT

                    # ✅ הדפסות DEBUG
                    print(f"[DEBUG] {sym} {position_side} | entry={entry_price}, mark={mark_price}, pnl={pnl_pct:.2f}%, threshold={threshold}, averages={averaging_counts[sym][position_side]}")

                    if pnl_pct <= -threshold and averaging_counts[sym][position_side] < MAX_AVERAGES_PER_POSITION:
                        try:
                            isolated_margin = float(pos.get('isolatedMargin', 0) or 0)
                        except:
                            isolated_margin = 0
                        if isolated_margin == 0:
                            try:
                                notional = abs(entry_price * amt)
                                isolated_margin = notional / LEVERAGE
                            except:
                                isolated_margin = 0

                        if isolated_margin <= 0:
                            logging.warning(f"לא ניתן לחשב margin עבור {sym}, מדלג על מיצוע (pnl={pnl_pct:.2f}%)")
                            print(f"[DEBUG] {sym} {position_side} | isolated_margin=0 → דילוג")
                        else:
                            print(f"📉 {sym} בהפסד {pnl_pct:.2f}% ({position_side}) — מבצע מיצוע...")
                            margin_to_use = isolated_margin * AVERAGING_MULTIPLIER
                            add_amount = (margin_to_use * LEVERAGE) / mark_price if mark_price > 0 else 0

                            symbol_info = symbols_info[sym]
                            step_size = None
                            min_qty = None
                            precision = 3
                            for f in symbol_info['filters']:
                                if f['filterType'] == 'LOT_SIZE':
                                    step_size = float(f['stepSize'])
                                    min_qty = float(f['minQty'])
                            if step_size:
                                add_amount = math.floor(add_amount / step_size) * step_size
                            try:
                                add_amount = round(add_amount, precision)
                            except:
                                pass

                            if not add_amount or add_amount <= 0 or (min_qty and add_amount < min_qty):
                                logging.warning(f"Add amount קטן מדי ל-{sym} ({add_amount}), מדלג על מיצוע")
                                print(f"[DEBUG] {sym} {position_side} | add_amount={add_amount} קטן מדי")
                            else:
                                try:
                                    resp = client.futures_create_order(
                                        symbol=sym,
                                        side=SIDE_BUY if position_side == 'LONG' else SIDE_SELL,
                                        type=ORDER_TYPE_MARKET,
                                        quantity=abs(add_amount),
                                        positionSide=position_side
                                    )
                                    averaging_counts[sym][position_side] += 1
                                    logging.info(f"Averaging order placed for {sym} {position_side} amount={add_amount} resp={resp}")
                                    print(f"✅ מיצוע #{averaging_counts[sym][position_side]} עבור {sym} ({position_side})")
                                except Exception as e:
                                    logging.error(f"כשל ביצירת הזמנת מיצוע ל-{sym}: {e}")
                                    continue

                                # עדכון TP חדש לאחר מיצוע
                                try:
                                    positions_after = client.futures_position_information(symbol=sym)
                                    new_entry = None
                                    new_amt = None
                                    for p2 in positions_after:
                                        if p2.get('positionSide') == position_side:
                                            new_entry = float(p2.get('entryPrice', 0) or 0)
                                            new_amt = float(p2.get('positionAmt', 0) or 0)
                                            break
                                    if new_entry and new_amt and abs(new_amt) > 0:
                                        new_tp_raw = new_entry * tp_multiplier
                                        tick = get_tick_size(symbol_info)
                                        new_tp = round_price_by_tick(new_tp_raw, tick)
                                        if tick and tick > 0:
                                            if position_side == 'LONG' and new_tp < new_tp_raw:
                                                new_tp += tick
                                            if position_side == 'SHORT' and new_tp > new_tp_raw:
                                                new_tp -= tick
                                        if new_tp <= 0:
                                            new_tp = new_tp_raw
                                        cancel_orders_for_symbol(sym, position_side=position_side)
                                        try:
                                            client.futures_create_order(
                                                symbol=sym,
                                                side=SIDE_SELL if position_side == 'LONG' else SIDE_BUY,
                                                type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                                                stopPrice=float(round(new_tp, 8)),
                                                closePosition=True,
                                                positionSide=position_side,
                                                workingType='MARK_PRICE'
                                            )
                                            logging.info(f"Updated TP for {sym} {position_side} to {new_tp} after averaging")
                                            print(f"🔄 עודכן TP חדש על {new_tp} ל-{sym} ({position_side})")
                                        except Exception as e:
                                            logging.error(f"כשל בהגדרת TP לאחר מיצוע ל-{sym}: {e}")
                                except Exception as ee:
                                    logging.error(f"כשל בעדכון פוזיציה לאחר מיצוע ל-{sym}: {ee}")

    except Exception as e:
        logging.error(f"שגיאה במעקב פוזיציות: {e}")
        print(f"שגיאה במעקב פוזיציות: {e}")

# --- MAIN ---
def main():
    ensure_hedge_mode()
    symbols_info = get_futures_symbols()
    print(f"נמצאו {len(symbols_info)} סימבולים פעילים.")
    last_monitor = time.time()

    while True:
        if ENABLE_MONITOR and (time.time() - last_monitor >= 60):
            monitor_positions(symbols_info)
            last_monitor = time.time()

        open_positions = get_open_positions()
        total_long_trades = sum(1 for sym in open_positions if open_positions[sym]["LONG"] != 0)
        total_short_trades = sum(1 for sym in open_positions if open_positions[sym]["SHORT"] != 0)

        if (MAX_LONG_TRADES > 0 and total_long_trades >= MAX_LONG_TRADES) and \
           (MAX_SHORT_TRADES > 0 and total_short_trades >= MAX_SHORT_TRADES):
            print(f"⚠️ הגעת למקסימום לונגים ({MAX_LONG_TRADES}) ושורטים ({MAX_SHORT_TRADES}), ממתין...")
            time.sleep(SCAN_INTERVAL)
            continue

        print("\n🔎 סריקה חדשה...")
        results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(check_symbol, sym, info): sym for sym, info in symbols_info.items()}
            for f in as_completed(futures):
                sym, change, open_price, close_price, kline_time = f.result()
                if change is not None:
                    print(f"{sym}: שינוי נר חי = {change:.2f}% (פתיחה {open_price}, נוכחי {close_price})")
                    results.append((sym, change, open_price, close_price, kline_time))

        for sym, change, open_price, close_price, kline_time in sorted(results, key=lambda x: x[1]):
            if handled_candles.get(sym) == kline_time:
                continue

            # --- LONG ---
            if change <= -DROP_TRIGGER:
                sma = get_sma(sym, 150)
                if sma and close_price < sma:
                    if MAX_LONG_TRADES == 0:
                        continue  # לא נכנס לונג אם מוגבל ל-0
                    if total_long_trades >= MAX_LONG_TRADES:
                        continue
                    if open_positions.get(sym, {}).get("LONG", 0) == 0:
                        handled_candles[sym] = kline_time
                        success = open_position(sym, close_price, symbols_info[sym], SIDE_BUY, 'LONG')
                        if success:
                            if sym not in open_positions:
                                open_positions[sym] = {"LONG": 0, "SHORT": 0}
                            open_positions[sym]["LONG"] = 1
                            total_long_trades += 1

            # --- SHORT ---
            elif change >= RISE_TRIGGER:
                sma = get_sma(sym, 150)
                if sma and close_price > sma:
                    if MAX_SHORT_TRADES == 0:
                        continue  # לא נכנס שורט אם מוגבל ל-0
                    if total_short_trades >= MAX_SHORT_TRADES:
                        continue
                    if open_positions.get(sym, {}).get("SHORT", 0) == 0:
                        handled_candles[sym] = kline_time
                        success = open_position(sym, close_price, symbols_info[sym], SIDE_SELL, 'SHORT')
                        if success:
                            if sym not in open_positions:
                                open_positions[sym] = {"LONG": 0, "SHORT": 0}
                            open_positions[sym]["SHORT"] = -1
                            total_short_trades += 1

        results_sorted = sorted(results, key=lambda x: x[1])
        print("\n🔥 3 הסימבולים עם הירידה הכי גדולה:")
        for s in results_sorted[:3]:
            print(f"{s[0]}: {s[1]:.2f}%")
        results_sorted_rise = sorted(results, key=lambda x: x[1], reverse=True)
        print("\n📈 3 הסימבולים עם העלייה הכי גדולה:")
        for s in results_sorted_rise[:3]:
            print(f"{s[0]}: {s[1]:.2f}%")

        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
