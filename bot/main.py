import asyncio
import os
import structlog
from bot.database.database_service import create_tables, TradeRepository
from bot.logic.trade_manager import TradeManager
from bot.logic.signal_engine import check_entry_conditions
from bot.logic.dca_engine import check_dca_conditions
from bot.exchange.binance_service import get_usdt_pairs, filter_by_volume
from bot.exchange.websocket_manager import PriceCache
from bot.notifications.telegram_service import TelegramService

logger = structlog.get_logger(__name__)

class TradingEngine:
    def __init__(self, config, client):
        self.config = config
        self.client = client
        self.manager = TradeManager(client, config.model_dump())
        self.price_cache = PriceCache(client)
        self.running = True
        
        token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.telegram = TelegramService(token) if token else None

    async def run(self):
        await self.initialize()
        iteration = 0
        
        while self.running:
            try:
                # בדיקת בריאות Websocket
                if not self.price_cache.is_healthy():
                    logger.warning("stale_market_data_skipping_cycle")
                    await asyncio.sleep(10)
                    continue

                open_trades = await TradeRepository.get_open_trades()
                
                # --- לוגיקת DCA: ניהול פוזיציות קיימות ---
                for trade in open_trades:
                    # בדיקה האם הגענו למקסימום מדרגות DCA
                    if trade['dca_count'] >= len(self.config.dca_scales):
                        continue
                        
                    if await check_dca_conditions(self.client, trade['symbol'], self.config.model_dump(), trade['avg_price']):
                        success = await self.manager.execute_dca_buy(trade)
                        if success:
                            await self.notify(f"📉 DCA בוצע: <b>{trade['symbol']}</b> (מדרגה {trade['dca_count'] + 1})")

                # --- לוגיקת כניסה: חיפוש הזדמנויות חדשות ---
                if len(open_trades) < self.config.max_positions:
                    await self._scan_for_new_entries(open_trades)

                # סינכרון פקודות TP פעם ב-10 איטרציות
                if iteration % 10 == 0:
                    await self.reconcile()

                iteration += 1
                await asyncio.sleep(self.config.sleep_interval)
                
            except Exception as e:
                logger.error("engine_loop_error", error=str(e))
                await asyncio.sleep(15)

    async def _scan_for_new_entries(self, open_trades):
        all_symbols = await get_usdt_pairs(self.client, self.config)
        vetted = await filter_by_volume(self.client, all_symbols, float(self.config.min_24h_volume))
        
        for symbol in vetted:
            if any(t['symbol'] == symbol for t in open_trades): continue
            
            # אופטימיזציה: העברת ה-price_cache כדי למנוע קריאות API מיותרות
            if await check_entry_conditions(self.client, symbol, self.config.model_dump()):
                success = await self.manager.open_trade(symbol)
                if success:
                    await self.notify(f"✅ עסקה חדשה: <b>{symbol}</b>")
                    break

    async def initialize(self):
        logger.info("system_startup")
        await create_tables()
        await self.price_cache.start()
        await self.reconcile()
        await self.notify("הבוט עלה לאוויר עם הגנות ייצור! 🚀")

    async def reconcile(self):
        """סנכרון מצב קיים ואימות פקודות TP"""
        trades = await TradeRepository.get_open_trades()
        for t in trades:
            if self.config.dry_run: continue
            try:
                order = await self.client.get_order(symbol=t['symbol'], orderId=t['tp_order_id'])
                if order and order['status'] == 'FILLED':
                    await TradeRepository.close_trade(t['id'], "CLOSED_PROFIT")
                    await self.notify(f"💰 רווח מומש: <b>{t['symbol']}</b>")
            except Exception as e:
                logger.error("reconcile_error", symbol=t['symbol'], error=str(e))

    async def notify(self, message: str):
        if self.telegram and self.chat_id:
            await self.telegram.send_message(self.chat_id, f"🤖 <b>SpotBot:</b>\n{message}")

# --- חלק ההרצה (נוסף על ידי Gemini) ---
if __name__ == "__main__":
    import yaml
    from dotenv import load_dotenv
    from binance import AsyncClient
    from bot.config_model import BotConfig

    # טעינת משתני סביבה
    load_dotenv()

    async def main():
        # בדיקה שקובץ הקונפיגורציה קיים
        if not os.path.exists("config/config.yaml"):
            print("Error: Config file not found in config/config.yaml")
            return

        # טעינת קונפיגורציה
        with open("config/config.yaml", "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
        
        # אימות קונפיגורציה מול המודל
        try:
            config = BotConfig(**raw_config)
        except Exception as e:
            print(f"Config validation error: {e}")
            return

        # יצירת קליינט בינאנס
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        
        if not api_key or not api_secret:
            print("Error: Missing BINANCE_API_KEY or BINANCE_API_SECRET in .env file")
            return

        client = await AsyncClient.create(api_key, api_secret)
        
        try:
            # יצירת המנוע והרצה
            engine = TradingEngine(config, client)
            await engine.run()
        except Exception as e:
            print(f"Fatal error: {e}")
        finally:
            await client.close_connection()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")