import asyncio
import logging
import yaml
import os
import datetime
from binance import AsyncClient
from dotenv import load_dotenv
from bot.exchange.binance_service import get_usdt_pairs, filter_by_volume, get_order
from bot.logic.signal_engine import check_entry_conditions
from bot.logic.trade_manager import open_trade, place_take_profit_order, dca, get_total_balance, get_symbol_info, round_quantity
from bot.logic.dca_engine import check_dca_conditions
from bot.risk.risk_manager import calculate_total_equity
from bot.database.database_service import create_tables, insert_trade, insert_order, get_open_trades, update_trade_tp_order_id, update_trade_status
from bot.notifications.telegram_service import TelegramService

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define trade states
TRADE_STATE_OPEN = "OPEN"
TRADE_STATE_CLOSED_PROFIT = "CLOSED_PROFIT"
TRADE_STATE_CLOSED_ABORTED = "CLOSED_ABORTED"

async def main():
    logging.info("Starting RDR2-Spot Bot...")
    try:
        # Load configuration from YAML file
        with open("bot/config/config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        logging.info("Configuration loaded from config.yaml")

        # Access environment variables
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        telegram_token = os.getenv("TELEGRAM_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")  # Add chat ID to .env

        # Initialize Binance client
        client = await AsyncClient.create(api_key=api_key, api_secret=api_secret)
        logging.info("Binance client initialized.")

        # Initialize Telegram bot
        telegram_service = TelegramService(telegram_token)
        logging.info("Telegram bot initialized.")

        # Initialize database
        await create_tables()

        # Get USDT pairs
        usdt_pairs = await get_usdt_pairs(client, config)

        # Filter by volume
        min_volume = config['min_24h_volume']
        symbols = await filter_by_volume(client, usdt_pairs, min_volume)

        logging.info(f"Tradable symbols: {symbols}")

        # Initialize variables for daily loss limit
        initial_balance = await get_total_balance(client)
        daily_loss_limit = config['daily_loss_limit'] / 100
        daily_initial_equity = initial_balance
        daily_loss_limit_reached = False

        # Get open trades from the database
        open_trades_db = await get_open_trades()
        open_trades = {trade['symbol']: {"quantity": trade['base_qty'], "avg_price": trade['avg_price'], 'trade_id': trade['id'], 'tp_order_id': trade['tp_order_id']} for trade in open_trades_db}
        logging.info(f"Loaded {len(open_trades)} open trades from the database.")

        # Recover open trades
        for symbol, trade_data in open_trades.items():
            try:
                tp_order_id = trade_data['tp_order_id']
                if tp_order_id:
                    tp_order = await get_order(client, symbol, tp_order_id)
                    if tp_order:
                        if tp_order['status'] == 'FILLED':
                            logging.info(f"Trade {trade_data['trade_id']} for {symbol} was closed with profit during downtime.")
                            await update_trade_status(trade_data['trade_id'], TRADE_STATE_CLOSED_PROFIT)
                            del open_trades[symbol]  # Remove from memory
                        elif tp_order['status'] == 'CANCELED':
                            logging.info(f"Take profit order {tp_order_id} for {symbol} was canceled during downtime.")
                            await update_trade_status(trade_data['trade_id'], TRADE_STATE_OPEN)
                        else:
                            logging.info(f"Take profit order {tp_order_id} for {symbol} is still active.")
                    else:
                        logging.warning(f"Could not retrieve take profit order {tp_order_id} for {symbol}. Assuming it was filled.")
                        await update_trade_status(trade_data['trade_id'], TRADE_STATE_CLOSED_PROFIT)
                        del open_trades[symbol]  # Remove from memory
            except Exception as e:
                logging.error(f"Error recovering trade {trade_data['trade_id']} for {symbol}: {e}")

        # Initialize error counter
        consecutive_errors = 0
        max_consecutive_errors = 10

        # Check entry conditions for each symbol
        last_day = datetime.datetime.utcnow().day
        while True:
            try:
                # Check if it's a new day
                current_day = datetime.datetime.utcnow().day
                if current_day != last_day:
                    logging.info("New day, resetting daily loss limit.")
                    daily_initial_equity = await calculate_total_equity(client, open_trades, initial_balance)
                    daily_loss_limit_reached = False
                    last_day = current_day

                    # Send daily report
                    total_equity = await calculate_total_equity(client, open_trades, initial_balance)
                    daily_report = f"Daily report:\nInitial equity: {daily_initial_equity}\nTotal equity: {total_equity}" # Removed extra parenthesis
                    await telegram_service.send_message(telegram_chat_id, daily_report)

                    # Refresh symbol list
                    usdt_pairs = await get_usdt_pairs(client, config)
                    min_volume = config['min_24h_volume']
                    symbols = await filter_by_volume(client, usdt_pairs, min_volume)
                    logging.info(f"Refreshed tradable symbols: {symbols}")

                for symbol in symbols:
                    if not daily_loss_limit_reached and symbol not in open_trades and await check_entry_conditions(client, symbol, config):
                        logging.info(f"Entry conditions met for {symbol}")
                        # Open trade
                        trade_details = await open_trade(client, symbol, config)
                        if trade_details:
                            logging.info(f"Trade opened for {symbol}: {trade_details}")
                            
                            trade_id = await insert_trade(symbol, TRADE_STATE_OPEN, trade_details["avg_price"], trade_details["quantity"], 0, 0)
                            open_trades[symbol] = {"quantity": trade_details["quantity"], "avg_price": trade_details["avg_price"], 'trade_id': trade_id, 'tp_order_id': None} # fixed syntax here.

                            # Send Telegram notification
                            message = f"<b>Trade opened</b>\nSymbol: {symbol}\nPrice: {trade_details['avg_price']}\nQuantity: {trade_details['quantity']}" #Fixed f-string
                            await telegram_service.send_message(telegram_chat_id, message)

                            # Place take profit order
                            tp_order = await place_take_profit_order(client, symbol, trade_details["quantity"], trade_details["avg_price"], config)
                            if tp_order:
                                logging.info(f"Take profit order placed for {symbol}: {tp_order}")
                                await insert_order(trade_id, tp_order['orderId'], 'TP', tp_order['price'], tp_order['origQty'], tp_order['status'])
                                await update_trade_tp_order_id(trade_id, tp_order['orderId'])
                                open_trades[symbol]['tp_order_id'] = tp_order['orderId']
                            else:
                                logging.error(f"Failed to place take profit order for {symbol}")
                                await telegram_service.send_message(telegram_chat_id, f"Failed to place take profit order for {symbol}")
                        else:
                            logging.error(f"Failed to open trade for {symbol}")
                            await telegram_service.send_message(telegram_chat_id, f"Failed to open trade for {symbol}")

                    elif symbol in open_trades and await check_dca_conditions(client, symbol, config, open_trades[symbol]["avg_price"]):
                        logging.info(f"DCA conditions met for {symbol}")
                        # Perform DCA
                        tp_order = await dca(client, symbol, config, open_trades[symbol]["quantity"], open_trades[symbol]["avg_price"], open_trades[symbol]['trade_id'], open_trades[symbol]['tp_order_id'], open_trades[symbol]['dca_count'])
                        if tp_order:
                            logging.info(f"DCA performed for {symbol}: {tp_order}")

                            # Update trade details with the new values
                            ticker = await client.get_ticker(symbol=symbol)
                            current_price = float(ticker['lastPrice'])
                            dca_quantity = open_trades[symbol]["quantity"] * config['dca_scales'][0]
                            new_avg_price = (open_trades[symbol]["avg_price"] * open_trades[symbol]["quantity"] + current_price * dca_quantity) / (open_trades[symbol]["quantity"] + dca_quantity)
                            open_trades[symbol]["avg_price"] = new_avg_price
                            open_trades[symbol]["quantity"] += dca_quantity

                            # Round quantity to step size
                            symbol_info = await get_symbol_info(client, symbol)
                            if symbol_info:
                                step_size = symbol_info['filters'][2]['stepSize']
                                open_trades[symbol]["quantity"] = await round_quantity(open_trades[symbol]["quantity"], step_size)

                            # Update DB
                            await update_trade_dca(open_trades[symbol]['trade_id'], new_avg_price, open_trades[symbol]["quantity"], open_trades[symbol]['dca_count'] + 1)  # increment dca_count
                            open_trades[symbol]['dca_count'] += 1  # update in memory

                            # Send Telegram notification
                            message = f"<b>DCA performed</b>\nSymbol: {symbol}\nNew average price: {open_trades[symbol]['avg_price']}\nNew quantity: {open_trades[symbol]['quantity']}"
                            await telegram_service.send_message(telegram_chat_id, message)
                        else:
                            logging.error(f"Failed to perform DCA for {symbol}")
                            await telegram_service.send_message(telegram_chat_id, f"Failed to perform DCA for {symbol}")

                    else:
                        logging.debug(f"No action for {symbol}")

                consecutive_errors = 0  # Reset error counter if no errors occurred
                await asyncio.sleep(60)  # Check every 60 seconds

            except Exception as e:
                logging.error(f"An error occurred: {e}")
                await telegram_service.send_message(telegram_chat_id, f"An error occurred: {e}")

                if consecutive_errors > max_consecutive_errors:
                    logging.critical(f"Too many consecutive errors ({consecutive_errors}). Stopping the bot.")
                    await telegram_service.send_message(telegram_chat_id, f"Too many consecutive errors ({consecutive_errors}). Stopping the bot.")
                    break
                consecutive_errors += 1
                await asyncio.sleep(60)  # Wait before retrying

        await client.close_connection()

    except Exception as e:
        logging.error(f"An error occurred: {e}")
