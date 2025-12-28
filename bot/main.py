import asyncio
import signal
import structlog
from bot.config_model import BotConfig
from bot.database.database_service import create_tables, TradeRepository
from bot.logic.trade_manager import TradeManager

logger = structlog.get_logger(__name__)

class TradingEngine:
    def __init__(self, config: BotConfig, client):
        self.config = config
        self.client = client
        # שימוש ב-model_dump במקום dict כדי למנוע אזהרות Pydantic V2
        self.manager = TradeManager(client, config.model_dump())
        self.running = True

    async def initialize(self):
        """הכנת המערכת לעבודה: יצירת טבלאות וסנכרון מול הבורסה"""
        logger.info("initializing_engine")
        await create_tables()
        await self.reconcile()

    async def reconcile(self):
        """Self-healing: בדיקה שכל פוזיציה ב-DB באמת קיימת בבורסה עם TP פעיל"""
        trades = await TradeRepository.get_open_trades()
        for t in trades:
            if self.config.dry_run: continue
            
            try:
                # בדיקה האם ה-TP עדיין קיים בבורסה
                order = await self.client.get_order(symbol=t['symbol'], orderId=t['tp_order_id'])
                if order['status'] == 'FILLED':
                    await TradeRepository.close_trade(t['id'], "CLOSED_PROFIT")
                    logger.info("reconcile_closed_trade", symbol=t['symbol'])
                elif order['status'] in ['CANCELED', 'EXPIRED', 'REJECTED']:
                    # שחזור פקודת TP שאבדה או בוטלה ידנית
                    logger.warning("reconcile_replacing_lost_tp", symbol=t['symbol'])
                    new_tp = await self.manager.place_tp_order(t['symbol'], t['base_qty'], t['avg_price'])
                    if new_tp:
                        await TradeRepository.update_trade_after_dca(t['id'], t['avg_price'], t['base_qty'], new_tp['orderId'])
            except Exception as e:
                logger.error("reconcile_error", symbol=t['symbol'], error=str(e))

    async def run(self):
        """לולאת המסחר המרכזית"""
        await self.initialize()
        
        while self.running:
            try:
                # כאן תבוצע הלוגיקה המחזורית (סריקה וניטור)
                await asyncio.sleep(self.config.sleep_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("loop_error", error=str(e))
                await asyncio.sleep(10)

    async def stop(self):
        self.running = False
        logger.info("shutting_down_gracefully")