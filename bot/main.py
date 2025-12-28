import asyncio
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

# הגדרת לוגים מובנים (Structured Logging)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
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

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((ClientError, Exception)),
)
async def api_call_with_retry(func, *args, **kwargs):
    return await asyncio.wait_for(func(*args, **kwargs), timeout=30)

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
        balance = await api_call_with_retry(get_total_balance, self.client, self.config, self.open_trades)
        self.daily_initial_equity = float(balance)
        usdt_pairs = await api_call_with_retry(get_usdt_pairs, self.client, self.config)
        self.symbols = await api_call_with_retry(filter_by_volume, self.client, usdt_pairs, self.config.min_24h_volume)

    async def reconcile_state(self):
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

    async def check_risk_limits(self):
        if self.daily_initial_equity <= 0: return
        total_equity = float(await api_call_with_retry(get_total_balance, self.client, self.config, self.open_trades))
        loss_percent = (self.daily_initial_equity - total_equity) / self.daily_initial_equity
        if not self.daily_loss_limit_reached and loss_percent >= self.config.daily_loss_limit / 100:
            self.daily_loss_limit_reached = True
            await self.telegram_service.send_message(self.chat_id, "🛑 Daily loss limit reached.")

    async def monitor_open_trades(self):
        for symbol, trade_data in list(self.open_trades.items()):
            try:
                if self.config.dry_run:
                    ticker = await api_call_with_retry(self.client.get_ticker, symbol=symbol)
                    filled = float(ticker["lastPrice"]) >= trade_data["tp_price"]
                else:
                    order = await api_call_with_retry(get_order, self.client, symbol, trade_data["tp_order_id"])
                    filled = order and order["status"] == "FILLED"
                
                if filled:
                    await update_trade_status(trade_data["trade_id"], TRADE_STATE_CLOSED_PROFIT)
                    del self.open_trades[symbol]
                    await self.telegram_service.send_message(self.chat_id, f"💰 Profit Taken: {symbol}")
            except Exception as e:
                self.logger.error("Monitor error", symbol=symbol, error=str(e))

    async def run(self):
        await self.initialize()
        while True:
            try:
                await self.check_risk_limits()
                await self.monitor_open_trades()
                await self.scan_opportunities()
                await asyncio.sleep(self.config.sleep_interval)
            except Exception as e:
                self.logger.error("Loop error", error=str(e))
                await asyncio.sleep(60)

    async def scan_opportunities(self):
        if self.daily_loss_limit_reached or len(self.open_trades) >= self.config.max_positions:
            return
        for symbol in self.symbols:
            if symbol in self.open_trades: continue
            if await api_call_with_retry(check_entry_conditions, self.client, symbol, self.config):
                trade = await api_call_with_retry(open_trade, self.client, symbol, self.config)
                if trade:
                    tp = await api_call_with_retry(place_take_profit_order, self.client, symbol, trade["quantity"], trade["avg_price"], self.config)
                    if tp:
                        t_id = await insert_trade(symbol, TRADE_STATE_OPEN, trade["avg_price"], trade["quantity"], 0, 0)
                        await update_trade_tp_order_id(t_id, tp["orderId"])
                        self.open_trades[symbol] = {
                            "quantity": trade["quantity"],
                            "avg_price": trade["avg_price"],
                            "trade_id": t_id,
                            "tp_order_id": tp["orderId"],
                            "tp_price": tp["price"] if "price" in tp else trade["avg_price"] * (1 + self.config.tp_percent / 100),
                            "dca_count": 0
                        }

async def main():
    try:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = BotConfig(**yaml.safe_load(f))
        
        client = await AsyncClient.create(api_key=os.getenv("BINANCE_API_KEY"), api_secret=os.getenv("BINANCE_API_SECRET"))
        telegram = TelegramService(os.getenv("TELEGRAM_TOKEN"))
        engine = TradingEngine(config, client, telegram, os.getenv("TELEGRAM_CHAT_ID"))
        await engine.run()
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(main())