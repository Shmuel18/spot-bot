import asyncio
import structlog
from binance import BinanceSocketManager
from decimal import Decimal

logger = structlog.get_logger(__name__)

class PriceCache:
    """מנהל מטמון מחירים שמתעדכן בזמן אמת דרך WebSockets"""
    def __init__(self, client):
        self.client = client
        self.bsm = BinanceSocketManager(client)
        self.prices = {}
        self._socket_task = None

    async def start(self):
        """מתחיל להאזין לעדכוני מחירים של כל השוק"""
        logger.info("starting_websocket_stream")
        try:
            # שימוש ב-multiplex_socket כדי להאזין לכל ה-tickers בצורה יציבה
            ts = self.bsm.all_ticker_socket()
            self._socket_task = asyncio.create_task(self._listen(ts))
        except Exception as e:
            logger.error("websocket_start_failed", error=str(e))

    async def _listen(self, ts):
        try:
            async with ts as tscm:
                while True:
                    res = await tscm.recv()
                    if isinstance(res, list):
                        for ticker in res:
                            # 's' = symbol, 'c' = current/close price
                            self.prices[ticker['s']] = Decimal(str(ticker['c']))
                    elif isinstance(res, dict) and res.get('e') == '24hrTicker':
                        self.prices[res['s']] = Decimal(str(res['c']))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("websocket_listen_error", error=str(e))

    def get_price(self, symbol: str) -> Decimal:
        """מחזיר את המחיר העדכני מהמטמון המקומי"""
        return self.prices.get(symbol)

    async def stop(self):
        if self._socket_task:
            self._socket_task.cancel()
            try:
                await self._socket_task
            except asyncio.CancelledError:
                pass