import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "trades.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       DATE    NOT NULL,
                ticker     TEXT    NOT NULL,
                name       TEXT    NOT NULL,
                side       TEXT    NOT NULL CHECK(side IN ('BUY','SELL')),
                price      INTEGER NOT NULL,
                amount     INTEGER NOT NULL,
                reason     TEXT,
                pnl        INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker       TEXT    NOT NULL UNIQUE,
                name         TEXT    NOT NULL,
                target_price INTEGER,
                stop_loss    INTEGER,
                memo         TEXT,
                added_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checklist_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker     TEXT    NOT NULL,
                date       DATE    NOT NULL,
                score      INTEGER NOT NULL,
                news_ok    BOOLEAN DEFAULT 0,
                volume_ok  BOOLEAN DEFAULT 0,
                surge_ok   BOOLEAN DEFAULT 0,
                naver_ok   BOOLEAN DEFAULT 0,
                cap_ok     BOOLEAN DEFAULT 0,
                no_chain   BOOLEAN DEFAULT 0,
                result     TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()

async def add_trade(date, ticker, name, side, price, amount, reason=""):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO trades (date,ticker,name,side,price,amount,reason) VALUES (?,?,?,?,?,?,?)",
            (date, ticker, name, side, price, amount, reason)
        )
        await conn.commit()

async def get_trades_by_date(date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM trades WHERE date=? ORDER BY created_at DESC", (date,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]

async def get_trades_all() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM trades ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]

async def update_trade_pnl(trade_id: int, pnl: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("UPDATE trades SET pnl=? WHERE id=?", (pnl, trade_id))
        await conn.commit()

async def delete_trade(trade_id: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
        await conn.commit()

async def add_watchlist(ticker: str, name: str, target_price: int = None, stop_loss: int = None, memo: str = ""):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO watchlist (ticker,name,target_price,stop_loss,memo) VALUES (?,?,?,?,?)",
            (ticker, name, target_price, stop_loss, memo)
        )
        await conn.commit()

async def get_watchlist() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]

async def remove_watchlist(ticker: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker,))
        await conn.commit()

async def save_checklist(ticker, date, score, news_ok, volume_ok, surge_ok, naver_ok, cap_ok, no_chain, result):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            INSERT INTO checklist_history
              (ticker,date,score,news_ok,volume_ok,surge_ok,naver_ok,cap_ok,no_chain,result)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (ticker, date, score, news_ok, volume_ok, surge_ok, naver_ok, cap_ok, no_chain, result))
        await conn.commit()
