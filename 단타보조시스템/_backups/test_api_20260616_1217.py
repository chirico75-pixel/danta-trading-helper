import pytest
from httpx import AsyncClient, ASGITransport
import database
import scheduler
import main as main_module
from kis_client import KISClient

class FakeWSManager:
    async def start(self): pass
    async def stop(self): pass
    async def subscribe(self, ticker): pass
    async def unsubscribe(self, ticker): pass

@pytest.fixture(autouse=True)
def use_tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "test")
    monkeypatch.setenv("KIS_APP_SECRET", "test")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "00000000-01")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(scheduler, "init_scheduler", lambda *a, **kw: None)
    monkeypatch.setattr(scheduler, "stop_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "WSManager", lambda *a, **kw: FakeWSManager())
    async def fake_approval_key(self): return "fake_key"
    monkeypatch.setattr(KISClient, "get_ws_approval_key", fake_approval_key)

@pytest.fixture
async def app():
    from main import app as fastapi_app
    from database import init_db
    await init_db()
    return fastapi_app

@pytest.mark.asyncio
async def test_add_trade(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/trades", json={
            "date": "2026-05-27",
            "ticker": "005930",
            "name": "삼성전자",
            "side": "BUY",
            "price": 75000,
            "amount": 5000000,
            "reason": "반도체 호재"
        })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

@pytest.mark.asyncio
async def test_get_trades(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/trades", json={
            "date": "2026-05-27", "ticker": "005930", "name": "삼성전자",
            "side": "BUY", "price": 75000, "amount": 5000000, "reason": ""
        })
        resp = await c.get("/api/trades?date=2026-05-27")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

@pytest.mark.asyncio
async def test_watchlist_add_remove(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/watchlist", json={
            "ticker": "005930", "name": "삼성전자",
            "target_price": 80000, "stop_loss": 70000
        })
        assert resp.status_code == 200
        resp2 = await c.get("/api/watchlist")
        assert len(resp2.json()) == 1
        resp3 = await c.delete("/api/watchlist/005930")
        assert resp3.status_code == 200
        resp4 = await c.get("/api/watchlist")
        assert len(resp4.json()) == 0
