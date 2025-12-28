import asyncio
import os
import structlog
from bot.config_model import BotConfig
from bot.database.database_service import create_tables, TradeRepository
from bot.logic.trade_manager import TradeManager
from bot.logic.signal_engine import check_entry_conditions
from bot.exchange.binance_service import get_usdt_pairs, filter_by_volume
from bot.exchange.websocket_manager import PriceCache
from bot.notifications.telegram_service import TelegramService

logger = structlog.get_logger(__name__)

class TradingEngine:
    def __init__(self, config: BotConfig, client):
        self.config = config
        self.client = client
        self.manager = TradeManager(client, config.model_dump())
        self.price_cache = PriceCache(client)
        self.running = True
        
        token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.telegram = TelegramService(token) if token else None

    async def notify(self, message: str):
        if self.telegram and self.chat_id:
            try:
                await self.telegram.send_message(self.chat_id, f"🤖 <b>SpotBot:</b>\n{message}")
            except Exception as e:
                logger.error("telegram_notify_error", error=str(e))

    async def initialize(self):
        logger.info("system_startup")
        await create_tables()
        await self.price_cache.start()
        await self.reconcile()
        await self.notify("הבוט עלה לאוויר ומתחיל לסרוק הזדמנויות! 🚀")

    async def reconcile(self):
        """סינכרון מצב קיים מול הבורסה למניעת פוזיציות יתומות"""
        trades = await TradeRepository.get_open_trades()
        for t in trades:
            if self.config.dry_run: continue
            try:
                order = await self.client.get_order(symbol=t['symbol'], orderId=t['tp_order_id'])
                if order and order['status'] == 'FILLED':
                    await TradeRepository.close_trade(t['id'], "CLOSED_PROFIT")
                    await self.notify(f"💰 עסקה נסגרת ברווח: <b>{t['symbol']}</b>")
                elif order and order['status'] in ['CANCELED', 'EXPIRED', 'REJECTED']:
                    logger.warning("reconcile_replacing_lost_tp", symbol=t['symbol'])
                    new_tp = await self.manager.place_tp_order(t['symbol'], t['base_qty'], t['avg_price'])
                    if new_tp:
                        await TradeRepository.confirm_trade(t['id'], t['avg_price'], t['base_qty'], new_tp['orderId'])
            except Exception as e:
                logger.error("reconcile_error", symbol=t['symbol'], error=str(e))

    async def run(self):
        await self.initialize()
        while self.running:
            try:
                open_trades = await TradeRepository.get_open_trades()
                if len(open_trades) < self.config.max_positions:
                    all_symbols = await get_usdt_pairs(self.client, self.config)
                    vetted = await filter_by_volume(self.client, all_symbols, float(self.config.min_24h_volume))
                    
                    for symbol in vetted:
                        if any(t['symbol'] == symbol for t in open_trades): continue
                        if await check_entry_conditions(self.client, symbol, self.config.model_dump()):
                            success = await self.manager.open_trade(symbol)
                            if success:
                                await self.notify(f"✅ נפתחה עסקה חדשה: <b>{symbol}</b>")
                                break 
                await asyncio.sleep(self.config.sleep_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("fatal_loop_error", error=str(e))
                await asyncio.sleep(10)

    async def stop(self):
        self.running = False
        await self.price_cache.stop()
        logger.info("shutting_down_gracefully")