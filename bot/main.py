import asyncio
import logging
import yaml
import os
import datetime
from pathlib import Path
from binance import AsyncClient
from dotenv import load_dotenv
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from aiohttp import ClientError

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
from bot.config_model import BotConfig

load_dotenv()

# Structured logging setup
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

TRADE_STATE_OPEN = "OPEN"
TRADE_STATE_CLOSED_PROFIT = "CLOSED_PROFIT"

# Circuit breaker for API calls
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((ClientError, Exception)),
)
async def api_call_with_retry(func, *args, **kwargs):
    return await asyncio.wait_for(func(*args, **kwargs), timeout=30)

TRADE_STATE_OPEN = "OPEN"
TRADE_STATE_CLOSED_PROFIT = "CLOSED_PROFIT"

class TradingEngine:
    def __init__(self, config: BotConfig, client: AsyncClient, telegram_service: TelegramService, chat_id: str):
        self.config = config
        self.client = client
        self.telegram_service = telegram_service
        self.chat_id = chat_id
        self.open_trades = {}
        self.daily_initial_equity = 0.0
        self.daily_loss_limit_reached = False
        self.last_day = datetime.datetime.now(datetime.timezone.utc).day
        self.symbols = []
        self.logger = logger.bind(component="TradingEngine")

    async def initialize(self):
        self.logger.info("Initializing TradingEngine")
        await create_tables()
        await self.reconcile_state()
        self.daily_initial_equity = await api_call_with_retry(get_total_balance, self.client, self.config, self.open_trades)
        usdt_pairs = await api_call_with_retry(get_usdt_pairs, self.client, self.config)
        self.symbols = await api_call_with_retry(filter_by_volume, self.client, usdt_pairs, self.config.min_24h_volume)
        self.logger.info("TradingEngine initialized", open_trades_count=len(self.open_trades), symbols_count=len(self.symbols))

    async def reconcile_state(self):
        """Reconcile DB state with Binance open orders on startup."""
        self.logger.info("Starting state reconciliation")
        open_trades_db = await get_open_trades()
        self.open_trades = {
            trade["symbol"]: {
                "quantity": trade["base_qty"],
                "avg_price": trade["avg_price"],
                "trade_id": trade["id"],
                "tp_order_id": trade["tp_order_id"],
                "tp_price": trade["avg_price"] * (1 + self.config.tp_percent / 100),
                "dca_count": trade["dca_count"],
            }
            for trade in open_trades_db
        }

        # Query open orders from Binance
        try:
            open_orders = await api_call_with_retry(self.client.get_open_orders)
            binance_open_symbols = {order['symbol'] for order in open_orders}
            db_open_symbols = set(self.open_trades.keys())

            # Find discrepancies
            missing_in_db = binance_open_symbols - db_open_symbols
            extra_in_db = db_open_symbols - binance_open_symbols

            if missing_in_db:
                self.logger.warning("Orders open on Binance but not in DB", symbols=list(missing_in_db))
                # For now, log; in production, might need to add them or alert

            if extra_in_db:
                self.logger.warning("Trades in DB but no open orders on Binance", symbols=list(extra_in_db))
                # Mark as closed or investigate

        except Exception as e:
            self.logger.error("Failed to reconcile state", error=str(e))

    async def check_daily_reset(self):
        current_day = datetime.datetime.now(datetime.timezone.utc).day
        if current_day != self.last_day:
            self.daily_initial_equity = await api_call_with_retry(get_total_balance, self.client, self.config, self.open_trades)
            self.daily_loss_limit_reached = False
            self.last_day = current_day
            self.logger.info("Daily reset", new_equity=self.daily_initial_equity)

    async def check_risk_limits(self):
        total_equity = await api_call_with_retry(get_total_balance, self.client, self.config, self.open_trades)
        loss_percent = (self.daily_initial_equity - total_equity) / self.daily_initial_equity
        if not self.daily_loss_limit_reached and loss_percent >= self.config.daily_loss_limit / 100:
            self.daily_loss_limit_reached = True
            await self.telegram_service.send_message(self.chat_id, "🛑 Daily loss limit reached. Stopping new trades.")
            self.logger.warning("Daily loss limit reached", loss_percent=loss_percent)

    async def monitor_open_trades(self):
        for symbol, trade_data in list(self.open_trades.items()):
            # Check TP
            try:
                if self.config.dry_run:
                    ticker = await api_call_with_retry(self.client.get_ticker, symbol=symbol)
                    filled = float(ticker["lastPrice"]) >= trade_data["tp_price"]
                else:
                    order_status = await api_call_with_retry(get_order, self.client, symbol, trade_data["tp_order_id"])
                    filled = order_status and order_status["status"] == "FILLED"
                if filled:
                    self.logger.info("TP filled", symbol=symbol)
                    await update_trade_status(trade_data["trade_id"], TRADE_STATE_CLOSED_PROFIT)
                    del self.open_trades[symbol]
                    await self.telegram_service.send_message(self.chat_id, f"💰 Profit Taken: {symbol}")
                    continue
            except Exception as e:
                self.logger.error("Error checking TP", symbol=symbol, error=str(e))

            # Check DCA
            try:
                if await api_call_with_retry(check_dca_conditions, self.client, symbol, self.config, trade_data["avg_price"]):
                    res = await api_call_with_retry(
                        dca,
                        self.client,
                        symbol,
                        self.config,
                        trade_data["quantity"],
                        trade_data["avg_price"],
                        trade_data["trade_id"],
                        trade_data["tp_order_id"],
                        trade_data["dca_count"],
                    )
                    if res:
                        self.open_trades[symbol].update(
                            {
                                "avg_price": res["new_avg_price"],
                                "quantity": res["new_quantity"],
                                "tp_order_id": res["tp_order"]["orderId"],
                                "dca_count": trade_data["dca_count"] + 1,
                            }
                        )
                        await update_trade_dca(trade_data["trade_id"], res["new_avg_price"], res["new_quantity"], 1)
                        self.logger.info("DCA executed", symbol=symbol, dca_count=trade_data["dca_count"] + 1)
            except Exception as e:
                self.logger.error("Error checking DCA", symbol=symbol, error=str(e))

    async def scan_opportunities(self):
        if self.daily_loss_limit_reached or len(self.open_trades) >= self.config.max_positions:
            return

        for symbol in self.symbols:
            if symbol in self.open_trades:
                continue
            try:
                if await api_call_with_retry(check_entry_conditions, self.client, symbol, self.config):
                    trade = await api_call_with_retry(open_trade, self.client, symbol, self.config)
                    if trade:
                        tp = await api_call_with_retry(
                            place_take_profit_order,
                            self.client, symbol, trade["quantity"], trade["avg_price"], self.config
                        )
                        if tp:
                            t_id = await insert_trade(
                                symbol, TRADE_STATE_OPEN, trade["avg_price"], trade["quantity"], 0, 0
                            )
                            await update_trade_tp_order_id(t_id, tp["orderId"])
                            self.open_trades[symbol] = {
                                "quantity": trade["quantity"],
                                "avg_price": trade["avg_price"],
                                "trade_id": t_id,
                                "tp_order_id": tp["orderId"],
                                "tp_price": tp["price"],
                                "dca_count": 0,
                            }
                            await self.telegram_service.send_message(self.chat_id, f"🚀 Entered Trade: {symbol}")
                            self.logger.info("New trade opened", symbol=symbol, trade_id=t_id)
            except Exception as e:
                self.logger.error("Error scanning opportunity", symbol=symbol, error=str(e))

    async def run(self):
        await self.initialize()
        while True:
            try:
                await self.check_daily_reset()
                await self.check_risk_limits()
                await self.monitor_open_trades()
                await self.scan_opportunities()
                await asyncio.sleep(self.config.sleep_interval)
            except Exception as e:
                self.logger.error("Loop error", error=str(e))
                await asyncio.sleep(60)


async def main():
    logger.info("Starting RDR2-Spot Bot...")
    try:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
        config = BotConfig(**config_data)

        client = await AsyncClient.create(
            api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_API_SECRET")
        )
        telegram_service = TelegramService(os.getenv("TELEGRAM_TOKEN"))
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        engine = TradingEngine(config, client, telegram_service, chat_id)
        await engine.run()

    except Exception as e:
        logger.error("Fatal error", error=str(e))


if __name__ == "__main__":
    asyncio.run(main())
