import asyncio
import logging
import aiosqlite

logger = logging.getLogger(__name__)

DATABASE_FILE = 'bot/database/trades.db'

async def create_tables():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                status TEXT NOT NULL,
                avg_price REAL NOT NULL,
                base_qty REAL NOT NULL,
                quote_spent REAL NOT NULL,
                dca_count INTEGER NOT NULL,
                tp_order_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL,
                binance_id TEXT NOT NULL,
                type TEXT NOT NULL,
                price REAL NOT NULL,
                qty REAL NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (trade_id) REFERENCES trades (id)
            )
        ''')
        await db.commit()
    logger.info("Database tables created.")

async def insert_trade(symbol: str, status: str, avg_price: float, base_qty: float, quote_spent: float, dca_count: int, tp_order_id: str = None):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        cursor = await db.execute(
            '''
            INSERT INTO trades (symbol, status, avg_price, base_qty, quote_spent, dca_count, tp_order_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (symbol, status, avg_price, base_qty, quote_spent, dca_count, tp_order_id)
        )
        await db.commit()
        trade_id = cursor.lastrowid
    logger.info(f"Inserted trade {trade_id} into the database.")
    return trade_id

async def update_trade_status(trade_id: int, status: str):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute(
            '''
            UPDATE trades SET status = ? WHERE id = ?
            ''',
            (status, trade_id)
        )
        await db.commit()
    logger.info(f"Updated trade {trade_id} status to {status}.")

async def update_trade_tp_order_id(trade_id: int, tp_order_id: str):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute(
            '''
            UPDATE trades SET tp_order_id = ? WHERE id = ?
            ''',
            (tp_order_id, trade_id)
        )
        await db.commit()
    logger.info(f"Updated trade {trade_id} tp_order_id to {tp_order_id}.")

async def insert_order(trade_id: int, binance_id: str, type: str, price: float, qty: float, status: str):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute(
            '''
            INSERT INTO orders (trade_id, binance_id, type, price, qty, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (trade_id, binance_id, type, price, qty, status)
        )
        await db.commit()
    logger.info(f"Inserted order {binance_id} into the database.")

async def get_open_trades():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT * FROM trades WHERE status NOT IN ('CLOSED_PROFIT', 'CLOSED_ABORTED')") as cursor:
            rows = await cursor.fetchall()
        trades = []
        for row in rows:
            trades.append({
                'id': row[0],
                'symbol': row[1],
                'status': row[2],
                'avg_price': row[3],
                'base_qty': row[4],
                'quote_spent': row[5],
                'dca_count': row[6],
                'tp_order_id': row[7],
                'created_at': row[8],
            })
    logger.info(f"Retrieved {len(trades)} open trades from the database.")
    return trades
