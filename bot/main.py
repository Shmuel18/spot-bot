import asyncio
import signal
from decimal import Decimal
from bot.config_model import BotConfig
from bot.database.database_service import create_tables, TradeRepository
from bot.logic.trade_manager import TradeManager
from bot.exchange.binance_service import get_usdt_pairs

class TradingEngine:
    def __init__(self, config: BotConfig, client):
        self.config = config
        self.client = client
        self.manager = TradeManager(client, config.dict())
        self.running = True

    async def reconcile(self):
        """Self-healing: בדיקה שכל פוזיציה ב-DB באמת קיימת בבורסה עם TP"""
        trades = await TradeRepository.get_open_trades()
        for t in trades:
            if self.config.dry_run: continue
            
            # בדיקה האם ה-TP עדיין קיים בבורסה
            try:
                order = await self.client.get_order(symbol=t['symbol'], orderId=t['tp_order_id'])
                if order['status'] == 'FILLED':
                    await TradeRepository.close_trade(t['id'], "CLOSED_PROFIT")
                elif order['status'] in ['CANCELED', 'EXPIRED']:
                    # שחזור TP שאבד
                    new_tp = await self.manager.place_tp_order(t['symbol'], t['base_qty'], t['avg_price'])
                    await TradeRepository.update_trade_after_dca(t['id'], t['avg_price'], t['base_qty'], new_tp['orderId'])
            except:
                logger.warning("could_not_reconcile_symbol", symbol=t['symbol'])

    async def run(self):
        await create_tables()
        await self.reconcile()
        
        while self.running:
            try:
                # לוגיקת סריקה וניטור (מקוצר לצורך הדוגמה)
                await self.monitor_trades()
                await self.scan_new_opportunities()
                await asyncio.sleep(self.config.sleep_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("loop_error", error=str(e))
                await asyncio.sleep(10)

    async def stop(self):
        self.running = False
        logger.info("shutting_down_gracefully")

async def main():
    # טעינת קונפיגורציה...
    # אתחול קליינט...
    
    engine = TradingEngine(config, client)
    
    # טיפול בסיגנלים של המערכת לסגירה בטוחה
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(engine.stop()))

    await engine.run()

if __name__ == "__main__":
    asyncio.run(main())