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
from bot.database.database_service import create_tables, insert_trade, get_open_trades, update_trade_tp_order_id, update_trade_status, update_trade_dca
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

        client = await AsyncClient.create(api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_API_SECRET"))
        telegram_service = TelegramService(os.getenv("TELEGRAM_TOKEN"))
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        await create_tables()

        # 1. טעינת עסקאות פתוחות
        open_trades_db = await get_open_trades()
        open_trades = {trade['symbol']: {
            "quantity": trade['base_qty'], "avg_price": trade['avg_price'], 
            'trade_id': trade['id'], 'tp_order_id': trade['tp_order_id'], 'dca_count': trade['dca_count']
        } for trade in open_trades_db}

        # 2. אתחול Equity וניהול סיכונים
        daily_initial_equity = await get_total_balance(client, config, open_trades)
        daily_loss_limit = config['daily_loss_limit'] / 100
        daily_loss_limit_reached = False
        last_day = datetime.datetime.utcnow().day

        usdt_pairs = await get_usdt_pairs(client, config)
        symbols = await filter_by_volume(client, usdt_pairs, config['min_24h_volume'])

        while True:
            try:
                # בדיקת יום חדש
                if datetime.datetime.utcnow().day != last_day:
                    daily_initial_equity = await get_total_balance(client, config, open_trades)
                    daily_loss_limit_reached = False
                    last_day = datetime.datetime.utcnow().day

                # בדיקת הפסד יומי ו-Equity נוכחי
                total_equity = await get_total_balance(client, config, open_trades)
                if not daily_loss_limit_reached and (daily_initial_equity - total_equity) / daily_initial_equity >= daily_loss_limit:
                    daily_loss_limit_reached = True
                    await telegram_service.send_message(chat_id, "🛑 Daily loss limit reached. Stopping new trades.")

                # ניטור עסקאות פתוחות (TP + DCA)
                for symbol, trade_data in list(open_trades.items()):
                    # בדיקה אם ה-TP הושלם
                    order_status = await get_order(client, symbol, trade_data['tp_order_id'])
                    if order_status and order_status['status'] == 'FILLED':
                        logging.info(f"✅ TP Filled for {symbol}")
                        await update_trade_status(trade_data['trade_id'], TRADE_STATE_CLOSED_PROFIT)
                        del open_trades[symbol]
                        await telegram_service.send_message(chat_id, f"💰 Profit Taken: {symbol}")
                        continue

                    # בדיקת DCA
                    if await check_dca_conditions(client, symbol, config, trade_data["avg_price"]):
                        res = await dca(client, symbol, config, trade_data["quantity"], trade_data["avg_price"], 
                                       trade_data['trade_id'], trade_data['tp_order_id'], trade_data['dca_count'])
                        if res:
                            open_trades[symbol].update({"avg_price": res['new_avg_price'], "quantity": res['new_quantity'], 
                                                       "tp_order_id": res['tp_order']['orderId'], "dca_count": trade_data['dca_count'] + 1})
                            await update_trade_dca(trade_data['trade_id'], res['new_avg_price'], res['new_quantity'], 1)

                # חיפוש הזדמנויות חדשות
                if not daily_loss_limit_reached and len(open_trades) < config['max_positions']:
                    for symbol in symbols:
                        if symbol not in open_trades and await check_entry_conditions(client, symbol, config):
                            trade = await open_trade(client, symbol, config)
                            if trade:
                                tp = await place_take_profit_order(client, symbol, trade["quantity"], trade["avg_price"], config)
                                if tp:
                                    t_id = await insert_trade(symbol, TRADE_STATE_OPEN, trade["avg_price"], trade["quantity"], 0, 0)
                                    await update_trade_tp_order_id(t_id, tp['orderId'])
                                    open_trades[symbol] = {"quantity": trade["quantity"], "avg_price": trade["avg_price"], 
                                                           "trade_id": t_id, "tp_order_id": tp['orderId'], "dca_count": 0}
                                    await telegram_service.send_message(chat_id, f"🚀 Entered Trade: {symbol}")

                await asyncio.sleep(config['sleep_interval'])
            except Exception as e:
                logging.error(f"Loop error: {e}")
                await asyncio.sleep(60)

    except Exception as e:
        logging.error(f"Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(main())