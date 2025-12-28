import structlog
import aiosqlite
import os
from decimal import Decimal

logger = structlog.get_logger(__name__)
DATABASE_FILE = os.getenv("DATABASE_FILE", "bot/database/trades.db")

async def create_tables():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                status TEXT NOT NULL, 
                avg_price TEXT NOT NULL, 
                base_qty TEXT NOT NULL,
                dca_count INTEGER NOT NULL,
                tp_order_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

class TradeRepository:
    @staticmethod
    async def create_pending_trade(symbol: str):
        async with aiosqlite.connect(DATABASE_FILE) as db:
            cursor = await db.execute(
                "INSERT INTO trades (symbol, status, avg_price, base_qty, dca_count) VALUES (?, 'PENDING_BUY', '0', '0', 0)",
                (symbol,)
            )
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def confirm_trade(trade_id: int, price: Decimal, qty: Decimal, tp_id: str, dca_count: int = 0):
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute(
                "UPDATE trades SET status = 'OPEN', avg_price = ?, base_qty = ?, tp_order_id = ?, dca_count = ? WHERE id = ?",
                (str(price), str(qty), tp_id, dca_count, trade_id)
            )
            await db.commit()

    @staticmethod
    async def get_open_trades():
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM trades WHERE status = 'OPEN'") as cursor:
                rows = await cursor.fetchall()
                return [{
                    "id": r["id"], "symbol": r["symbol"],
                    "avg_price": Decimal(r["avg_price"]), "base_qty": Decimal(r["base_qty"]),
                    "dca_count": r["dca_count"], "tp_order_id": r["tp_order_id"]
                } for r in rows]

    @staticmethod
    async def close_trade(trade_id: int, status: str):
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
            await db.commit()