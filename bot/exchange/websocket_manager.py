import asyncio
import structlog
from datetime import datetime, timezone
from binance import BinanceSocketManager
from decimal import Decimal

logger = structlog.get_logger(__name__)

class PriceCache:
    def __init__(self, client):
        self.client = client
        self.bsm = BinanceSocketManager(client)
        self.prices = {}
        self.last_update = None
        self._socket_task = None

    async def start(self):
        logger.info("starting_websocket_stream")
        try:
            ts = self.bsm.all_ticker_socket()
            self._socket_task = asyncio.create_task(self._listen(ts))
        except Exception as e:
            logger.error("websocket_start_failed", error=str(e))

    async def _listen(self, ts):
        try:
            async with ts as tscm:
                while True:
                    res = await tscm.recv()
                    self.last_update = datetime.now(timezone.utc)
                    if isinstance(res, list):
                        for ticker in res:
                            self.prices[ticker['s']] = Decimal(str(ticker['c']))
                    elif isinstance(res, dict) and res.get('e') == '24hrTicker':
                        self.prices[res['s']] = Decimal(str(res['c']))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("websocket_listen_error", error=str(e))

    def is_healthy(self, max_age_seconds=30) -> bool:
        """בדיקת דופק - האם קיבלנו עדכון מחיר לאחרונה"""
        if not self.last_update: return False
        age = (datetime.now(timezone.utc) - self.last_update).total_seconds()
        return age < max_age_seconds

    def get_price(self, symbol: str) -> Decimal:
        return self.prices.get(symbol)

    async def stop(self):
        if self._socket_task:
            self._socket_task.cancel()