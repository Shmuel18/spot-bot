import asyncio
import logging
import yaml
import os
import datetime
from pathlib import Path
from binance import AsyncClient
from dotenv import load_dotenv

from bot.exchange.binance_service import get_usdt_pairs, filter_by_volume, get_order
from bot.logic.signal_engine import check_entry_conditions
from bot.logic.trade_manager import open_trade, place_take_profit_order, dca, get_total_balance
from bot.logic.dca_engine import check_dca_conditions
from bot.database.database_service import (
    create_tables,
    insert_trade,
    get_open_trades,
    update_trade_tp_order_id,
    update_trade_status,
    update_trade_dca,
)
from bot.notifications.telegram_service import TelegramService

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TRADE_STATE_OPEN = "OPEN"
TRADE_STATE_CLOSED_PROFIT = "CLOSED_PROFIT"


def validate_config(config: dict):
    """
    Validate the configuration dictionary.

    Raises ValueError if invalid.
    """
    required_keys = [
        "timeframe",
        "sma_length",
        "dip_threshold",
        "position_size_percent",
        "tp_percent",
        "dca_scales",
        "dca_trigger",
        "max_positions",
        "min_24h_volume",
        "daily_loss_limit",
        "sleep_interval",
        "blacklist",
    ]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    if not isinstance(config["sma_length"], int) or config["sma_length"] <= 0:
        raise ValueError("sma_length must be a positive integer")

    if not isinstance(config["position_size_percent"], (int, float)) or not (
        0 < config["position_size_percent"] <= 100
    ):
        raise ValueError("position_size_percent must be between 0 and 100")

    if not isinstance(config["dca_scales"], list) or not all(isinstance(x, (int, float)) for x in config["dca_scales"]):
        raise ValueError("dca_scales must be a list of numbers")

    # Add more validations as needed


async def main():
    logging.info("Starting RDR2-Spot Bot...")
    try:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        validate_config(config)

        client = await AsyncClient.create(
            api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_API_SECRET")
        )
        telegram_service = TelegramService(os.getenv("TELEGRAM_TOKEN"))
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        await create_tables()

        # 1. Load open trades
        open_trades_db = await get_open_trades()
        open_trades = {
            trade["symbol"]: {
                "quantity": trade["base_qty"],
                "avg_price": trade["avg_price"],
                "trade_id": trade["id"],
                "tp_order_id": trade["tp_order_id"],
                "tp_price": trade["avg_price"] * (1 + config["tp_percent"] / 100),
                "dca_count": trade["dca_count"],
            }
            for trade in open_trades_db
        }

        # 2. Initialize Equity and risk management
        daily_initial_equity = await get_total_balance(client, config, open_trades)
        daily_loss_limit = config["daily_loss_limit"] / 100
        daily_loss_limit_reached = False
        last_day = datetime.datetime.now(datetime.timezone.utc).day

        usdt_pairs = await get_usdt_pairs(client, config)
        symbols = await filter_by_volume(client, usdt_pairs, config["min_24h_volume"])

        while True:
            try:
                # Check for new day
                if datetime.datetime.now(datetime.timezone.utc).day != last_day:
                    daily_initial_equity = await get_total_balance(client, config, open_trades)
                    daily_loss_limit_reached = False
                    last_day = datetime.datetime.now(datetime.timezone.utc).day

                # Check daily loss and current Equity
                total_equity = await get_total_balance(client, config, open_trades)
                if (
                    not daily_loss_limit_reached
                    and (daily_initial_equity - total_equity) / daily_initial_equity >= daily_loss_limit
                ):
                    daily_loss_limit_reached = True
                    await telegram_service.send_message(chat_id, "🛑 Daily loss limit reached. Stopping new trades.")

                # Monitor open trades (TP + DCA)
                for symbol, trade_data in list(open_trades.items()):
                    # Check if TP is filled
                    if config.get("dry_run", False):
                        ticker = await client.get_ticker(symbol=symbol)
                        filled = float(ticker["lastPrice"]) >= trade_data["tp_price"]
                    else:
                        order_status = await get_order(client, symbol, trade_data["tp_order_id"])
                        filled = order_status and order_status["status"] == "FILLED"
                    if filled:
                        logging.info(f"✅ TP Filled for {symbol}")
                        await update_trade_status(trade_data["trade_id"], TRADE_STATE_CLOSED_PROFIT)
                        del open_trades[symbol]
                        await telegram_service.send_message(chat_id, f"💰 Profit Taken: {symbol}")
                        continue

                    # Check DCA
                    if await check_dca_conditions(client, symbol, config, trade_data["avg_price"]):
                        res = await dca(
                            client,
                            symbol,
                            config,
                            trade_data["quantity"],
                            trade_data["avg_price"],
                            trade_data["trade_id"],
                            trade_data["tp_order_id"],
                            trade_data["dca_count"],
                        )
                        if res:
                            open_trades[symbol].update(
                                {
                                    "avg_price": res["new_avg_price"],
                                    "quantity": res["new_quantity"],
                                    "tp_order_id": res["tp_order"]["orderId"],
                                    "dca_count": trade_data["dca_count"] + 1,
                                }
                            )
                            await update_trade_dca(trade_data["trade_id"], res["new_avg_price"], res["new_quantity"], 1)

                # Search for new opportunities
                if not daily_loss_limit_reached and len(open_trades) < config["max_positions"]:
                    for symbol in symbols:
                        if symbol not in open_trades and await check_entry_conditions(client, symbol, config):
                            trade = await open_trade(client, symbol, config)
                            if trade:
                                tp = await place_take_profit_order(
                                    client, symbol, trade["quantity"], trade["avg_price"], config
                                )
                                if tp:
                                    t_id = await insert_trade(
                                        symbol, TRADE_STATE_OPEN, trade["avg_price"], trade["quantity"], 0, 0
                                    )
                                    await update_trade_tp_order_id(t_id, tp["orderId"])
                                    open_trades[symbol] = {
                                        "quantity": trade["quantity"],
                                        "avg_price": trade["avg_price"],
                                        "trade_id": t_id,
                                        "tp_order_id": tp["orderId"],
                                        "tp_price": tp["price"],
                                        "dca_count": 0,
                                    }
                                    await telegram_service.send_message(chat_id, f"🚀 Entered Trade: {symbol}")

                await asyncio.sleep(config["sleep_interval"])
            except Exception as e:
                logging.error(f"Loop error: {e}")
                await asyncio.sleep(60)

    except Exception as e:
        logging.error(f"Fatal error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
