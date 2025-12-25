import asyncio
import logging
import yaml
import os
import datetime
from binance import AsyncClient
from dotenv import load_dotenv
from bot.exchange.binance_service import get_usdt_pairs, filter_by_volume, get_order
from bot.logic.signal_engine import check_entry_conditions
from bot.logic.trade_manager import open_trade, place_take_profit_order, dca, get_total_balance
from bot.logic.dca_engine import check_dca_conditions

from bot.database.database_service import create_tables, insert_trade, insert_order, get_open_trades, update_trade_tp_order_id, update_trade_status, update_trade_dca
from bot.notifications.telegram_service import TelegramService

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TRADE_STATE_OPEN = "OPEN"
TRADE_STATE_CLOSED_PROFIT = "CLOSED_PROFIT"

async def main():
    logging.info("Starting RDR2-Spot Bot...")
    try:
        with open("bot/config/config.yaml", 'r') as f:
            config = yaml.safe_load(f)

        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        client = await AsyncClient.create(api_key=api_key, api_secret=api_secret)
        telegram_service = TelegramService(telegram_token)
        await create_tables()

        # 1. טעינת עסקאות פתוחות מה-DB (חובה לפני הכל)
        open_trades_db = await get_open_trades()
        open_trades = {trade['symbol']: {
            "quantity": trade['base_qty'], 
            "avg_price": trade['avg_price'], 
            'trade_id': trade['id'], 
            'tp_order_id': trade['tp_order_id'], 
            'dca_count': trade['dca_count']
        } for trade in open_trades_db}
        logging.info(f"Loaded {len(open_trades)} open trades from the database.")

        # 2. אתחול משתני ניהול סיכונים
        daily_loss_limit = config['daily_loss_limit'] / 100
        daily_initial_equity = await get_total_balance(client, config, open_trades)
        daily_loss_limit_reached = False

        # 3. שחזור עסקאות (Recovery)
        for symbol, trade_data in list(open_trades.items()):
            try:
                if trade_data['tp_order_id']:
                    tp_order = await get_order(client, symbol, trade_data['tp_order_id'])
                    if tp_order and tp_order['status'] == 'FILLED':
                        await update_trade_status(trade_data['trade_id'], TRADE_STATE_CLOSED_PROFIT)
                        del open_trades[symbol]
                    elif tp_order and tp_order['status'] == 'CANCELED':
                        # ניסיון להציב TP חדש אם הישן בוטל
                        new_tp = await place_take_profit_order(client, symbol, trade_data["quantity"], trade_data["avg_price"], config)
                        if new_tp:
                            await update_trade_tp_order_id(trade_data['trade_id'], new_tp['orderId'])
                            open_trades[symbol]['tp_order_id'] = new_tp['orderId']
            except Exception as e:
                logging.error(f"Recovery error for {symbol}: {e}")

        usdt_pairs = await get_usdt_pairs(client, config)
        symbols = await filter_by_volume(client, usdt_pairs, config['min_24h_volume'])
        
        last_day = datetime.datetime.utcnow().day
        consecutive_errors = 0

        while True:
            try:
                current_day = datetime.datetime.utcnow().day
                if current_day != last_day:
                    daily_initial_equity = await get_total_balance(client, config, open_trades)
                    daily_loss_limit_reached = False
                    last_day = current_day
                    logging.info("New day reset.")

                # בדיקת הפסד יומי בזמן אמת
                total_equity = await get_total_balance(client, config, open_trades)
                loss_ratio = (daily_initial_equity - total_equity) / daily_initial_equity if daily_initial_equity > 0 else 0
                if loss_ratio >= daily_loss_limit:
                    daily_loss_limit_reached = True

                for symbol in symbols:
                    if not daily_loss_limit_reached and symbol not in open_trades:
                        if await check_entry_conditions(client, symbol, config):
                            trade_details = await open_trade(client, symbol, config)
                            if trade_details:
                                tp_order = await place_take_profit_order(client, symbol, trade_details["quantity"], trade_details["avg_price"], config)
                                if tp_order:
                                    trade_id = await insert_trade(symbol, TRADE_STATE_OPEN, trade_details["avg_price"], trade_details["quantity"], 0, 0)
                                    await update_trade_tp_order_id(trade_id, tp_order['orderId'])
                                    open_trades[symbol] = {
                                        "quantity": trade_details["quantity"], 
                                        "avg_price": trade_details["avg_price"], 
                                        'trade_id': trade_id, 
                                        'tp_order_id': tp_order['orderId'], 
                                        'dca_count': 0
                                    }
                                    await telegram_service.send_message(telegram_chat_id, f"Trade opened: {symbol}")

                    elif symbol in open_trades:
                        if await check_dca_conditions(client, symbol, config, open_trades[symbol]["avg_price"]):
                            res = await dca(client, symbol, config, open_trades[symbol]["quantity"], open_trades[symbol]["avg_price"], 
                                           open_trades[symbol]['trade_id'], open_trades[symbol]['tp_order_id'], open_trades[symbol]['dca_count'])
                            if res:
                                open_trades[symbol].update({
                                    "avg_price": res['new_avg_price'],
                                    "quantity": res['new_quantity'],
                                    "tp_order_id": res['tp_order']['orderId'],
                                    "dca_count": open_trades[symbol]['dca_count'] + 1
                                })
                                await update_trade_dca(open_trades[symbol]['trade_id'], res['new_avg_price'], res['new_quantity'], 1)

                await asyncio.sleep(config['sleep_interval'])
                consecutive_errors = 0
            except Exception as e:
                logging.error(f"Loop error: {e}")
                consecutive_errors += 1
                if consecutive_errors > config['max_consecutive_errors']: break
                await asyncio.sleep(config['sleep_interval'])

        await client.close_connection()
    except Exception as e:
        logging.error(f"Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(main())