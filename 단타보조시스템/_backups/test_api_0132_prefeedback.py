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


@pytest.mark.asyncio
async def test_curriculum_get_and_toggle(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 초기 조회: 6단계, 전부 미완료
        r = await c.get("/api/curriculum")
        assert r.status_code == 200
        data = r.json()
        assert len(data["stages"]) == 6
        assert data["total"] == 14
        assert data["completed"] == 0
        assert data["percent"] == 0
        # 항목 1개 완료 토글
        r2 = await c.post("/api/curriculum/toggle", json={"item_key": "s1_screen", "done": True})
        assert r2.status_code == 200
        r3 = await c.get("/api/curriculum")
        d3 = r3.json()
        assert d3["completed"] == 1
        assert any(i["key"] == "s1_screen" and i["done"] for st in d3["stages"] for i in st["items"])
        # 잘못된 키는 404
        r4 = await c.post("/api/curriculum/toggle", json={"item_key": "nope", "done": True})
        assert r4.status_code == 404


@pytest.mark.asyncio
async def test_lectures_search(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 빈 검색어 → 빈 결과
        r0 = await c.get("/api/lectures/search?q=")
        assert r0.status_code == 200
        assert r0.json()["results"] == []
        # 검색어 → 200, 구조 정상 (테스트 환경엔 녹취록이 없어 결과 0일 수 있음)
        r1 = await c.get("/api/lectures/search?q=상한가")
        assert r1.status_code == 200
        d = r1.json()
        assert "results" in d and "lecture_count" in d and d["query"] == "상한가"
