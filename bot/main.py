import asyncio
import structlog
from bot.config_model import BotConfig
from bot.database.database_service import create_tables, TradeRepository
from bot.logic.trade_manager import TradeManager
from bot.logic.signal_engine import check_entry_conditions
from bot.exchange.binance_service import get_usdt_pairs, filter_by_volume

logger = structlog.get_logger(__name__)

class TradingEngine:
    def __init__(self, config: BotConfig, client):
        self.config = config
        self.client = client
        # שימוש ב-model_dump() לעבודה עם מילון עבור ה-Manager
        self.manager = TradeManager(client, config.model_dump())
        self.running = True

    async def initialize(self):
        """הכנת המערכת: יצירת טבלאות וסנכרון מול הבורסה"""
        logger.info("system_startup")
        await create_tables()
        # קריאה חיונית עבור ה-Integration Test ועבור שרידות המערכת
        await self.reconcile()

    async def reconcile(self):
        """בדיקה שכל פוזיציה ב-DB באמת קיימת בבורסה עם TP פעיל"""
        trades = await TradeRepository.get_open_trades()
        for t in trades:
            if self.config.dry_run: continue
            
            try:
                # בדיקה האם ה-TP עדיין קיים בבורסה
                order = await self.client.get_order(symbol=t['symbol'], orderId=t['tp_order_id'])
                if order and order['status'] == 'FILLED':
                    await TradeRepository.close_trade(t['id'], "CLOSED_PROFIT")
                    logger.info("reconcile_closed_trade", symbol=t['symbol'])
                elif order and order['status'] in ['CANCELED', 'EXPIRED', 'REJECTED']:
                    logger.warning("reconcile_replacing_lost_tp", symbol=t['symbol'])
                    new_tp = await self.manager.place_tp_order(t['symbol'], t['base_qty'], t['avg_price'])
                    if new_tp:
                        # עדכון ה-DB עם ה-ID של ה-TP החדש
                        await TradeRepository.confirm_trade(t['id'], t['avg_price'], t['base_qty'], new_tp['orderId'])
            except Exception as e:
                logger.error("reconcile_error", symbol=t['symbol'], error=str(e))

    async def run(self):
        """לולאת המסחר המרכזית"""
        await self.initialize()
        
        while self.running:
            try:
                # בדיקה של עסקאות פתוחות קיימות (DCA)
                open_trades = await TradeRepository.get_open_trades()
                
                # אם יש מקום לעסקאות חדשות
                if len(open_trades) < self.config.max_positions:
                    all_symbols = await get_usdt_pairs(self.client, self.config)
                    vetted_symbols = await filter_by_volume(self.client, all_symbols, float(self.config.min_24h_volume))
                    
                    for symbol in vetted_symbols:
                        # לא נפתח עסקה על מטבע שכבר פתוח
                        if any(t['symbol'] == symbol for t in open_trades): continue
                        
                        if await check_entry_conditions(self.client, symbol, self.config.model_dump()):
                            logger.info("entry_signal_detected", symbol=symbol)
                            await self.manager.open_trade(symbol)
                            break # פתיחת פוזיציה אחת בכל מחזור סריקה

                await asyncio.sleep(self.config.sleep_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("fatal_loop_error", error=str(e))
                await asyncio.sleep(10)

    async def stop(self):
        self.running = False
        logger.info("shutting_down_gracefully")