import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date as _date
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import database
from sse_broker import broker
from scheduler import init_scheduler, stop_scheduler, get_cached_ranking
from ws_manager import WSManager

load_dotenv()
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    app.state.ws_mgr = None
    app.state.kis = None
    try:
        from kis_client import create_client_from_env
        kis = create_client_from_env()
        app.state.kis = kis
        init_scheduler(kis, broker)
        try:
            approval_key = await kis.get_ws_approval_key()
            ws_mgr = WSManager(kis.ws_url, approval_key, broker)
            await ws_mgr.start()
            app.state.ws_mgr = ws_mgr
        except Exception as e:
            logging.warning(f"WebSocket manager could not start: {e}")

        if app.state.ws_mgr:
            try:
                existing = await database.get_watchlist()
                for item in existing:
                    await app.state.ws_mgr.subscribe(item['ticker'])
            except Exception as e:
                logging.warning(f"Watchlist re-subscribe failed: {e}")
    except KeyError:
        logging.warning("KIS API keys not set — polling disabled")
    yield
    stop_scheduler()
    if app.state.ws_mgr is not None:
        await app.state.ws_mgr.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ── SSE ──────────────────────────────────────────────
@app.get("/events")
async def sse_events():
    return StreamingResponse(broker.subscribe(),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ── 랭킹 ─────────────────────────────────────────────
@app.get("/api/ranking")
async def get_ranking(market: str = "ALL"):
    return get_cached_ranking(market)


# ── 강일지 ────────────────────────────────────────────
class TradeIn(BaseModel):
    date: str
    ticker: str
    name: str
    side: str
    price: int
    amount: int
    reason: str = ""

@app.post("/api/trades")
async def create_trade(body: TradeIn):
    await database.add_trade(body.date, body.ticker, body.name,
                             body.side, body.price, body.amount, body.reason)
    return {"ok": True}

@app.get("/api/trades")
async def list_trades(date: str = None):
    if date:
        return await database.get_trades_by_date(date)
    return await database.get_trades_all()

@app.delete("/api/trades/{trade_id}")
async def remove_trade(trade_id: int):
    await database.delete_trade(trade_id)
    return {"ok": True}


# ── 관심종목 ──────────────────────────────────────────
class WatchIn(BaseModel):
    ticker: str
    name: str
    target_price: Optional[int] = None
    stop_loss: Optional[int] = None
    memo: str = ""

@app.post("/api/watchlist")
async def add_watch(body: WatchIn, request: Request):
    await database.add_watchlist(body.ticker, body.name,
                                 body.target_price, body.stop_loss, body.memo)
    ws_mgr = getattr(request.app.state, 'ws_mgr', None)
    if ws_mgr:
        await ws_mgr.subscribe(body.ticker)
    return {"ok": True}

@app.get("/api/watchlist")
async def list_watch():
    return await database.get_watchlist()

@app.delete("/api/watchlist/{ticker}")
async def remove_watch(ticker: str, request: Request):
    await database.remove_watchlist(ticker)
    ws_mgr = getattr(request.app.state, 'ws_mgr', None)
    if ws_mgr:
        await ws_mgr.unsubscribe(ticker)
    return {"ok": True}


# ── 체크리스트 ────────────────────────────────────────
class CheckIn(BaseModel):
    ticker: str
    news_ok: bool
    naver_ok: bool

@app.post("/api/checklist")
async def run_checklist(body: CheckIn, request: Request):
    kis = request.app.state.kis
    if kis is None:
        raise HTTPException(status_code=503, detail="KIS API 미설정")
    try:
        info = await kis.get_price(body.ticker)
    except Exception:
        raise HTTPException(status_code=502, detail="KIS API 조회 실패")

    score = 0
    volume_ok = info["volume_ratio"] >= 3.0
    surge_ok  = info["change_rate"] >= 20.0
    cap_ok    = 0 < info["market_cap"] <= 100000
    no_chain  = info["change_rate"] < 29.5

    if body.news_ok:  score += 30
    if volume_ok:     score += 20
    if surge_ok:      score += 20
    if body.naver_ok: score += 15
    if cap_ok:        score += 10
    if no_chain:      score += 5

    result = "진입 검토" if score >= 70 else ("관망" if score >= 50 else "제외")

    await database.save_checklist(
        body.ticker, str(_date.today()), score,
        body.news_ok, volume_ok, surge_ok, body.naver_ok, cap_ok, no_chain, result
    )
    return {
        "ticker": body.ticker,
        "score": score,
        "result": result,
        "detail": {
            "news_ok": body.news_ok,
            "volume_ok": volume_ok,
            "surge_ok": surge_ok,
            "naver_ok": body.naver_ok,
            "cap_ok": cap_ok,
            "no_chain": no_chain,
        },
        "price_info": info,
    }


# ── 메인 페이지 ───────────────────────────────────────
@app.get("/")
async def root():
    path = BASE_DIR / "static" / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
