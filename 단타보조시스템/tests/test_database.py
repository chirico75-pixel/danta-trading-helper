import pytest
import pytest_asyncio
import database
from database import init_db, add_trade, get_trades_by_date, add_watchlist, get_watchlist, save_checklist

@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    await init_db()
    yield

@pytest.mark.asyncio
async def test_add_and_get_trade(db):
    await add_trade("2026-05-27", "005930", "삼성전자", "BUY", 75000, 5000000, "반도체 호재")
    trades = await get_trades_by_date("2026-05-27")
    assert len(trades) == 1
    assert trades[0]["ticker"] == "005930"
    assert trades[0]["pnl"] == 0

@pytest.mark.asyncio
async def test_add_and_get_watchlist(db):
    await add_watchlist("005930", "삼성전자", 80000, 70000)
    items = await get_watchlist()
    assert len(items) == 1
    assert items[0]["ticker"] == "005930"

@pytest.mark.asyncio
async def test_save_checklist(db):
    await save_checklist("005930", "2026-05-27", 85, True, True, True, True, False, True, "진입 검토")
    import aiosqlite
    async with aiosqlite.connect(database.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM checklist_history WHERE ticker='005930'") as cur:
            row = await cur.fetchone()
    assert row["score"] == 85
