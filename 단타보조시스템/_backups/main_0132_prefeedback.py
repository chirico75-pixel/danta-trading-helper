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
from scheduler import init_scheduler, stop_scheduler, get_cached_ranking, init_demo_scheduler, is_demo
from ws_manager import WSManager

load_dotenv()
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).parent

async def seed_demo_db():
    """데모 첫 기동 시 샘플 관심종목·강일지 시드(비어 있을 때만). demo_trades.db 한정."""
    try:
        if not await database.get_watchlist():
            await database.add_watchlist("247540", "에코프로비엠", 150000, 120000, "[데모] 2차전지 대장")
            await database.add_watchlist("042660", "한화오션", 45000, 33000, "[데모] 조선 테마")
        if not await database.get_trades_all():
            today = str(_date.today())
            await database.add_trade(today, "247540", "에코프로비엠", "BUY", 130000, 5000000, "[데모] 2차전지 테마 호재")
            await database.add_trade(today, "042660", "한화오션", "BUY", 36000, 3000000, "[데모] 조선 수주 기대")
            await database.add_trade(today, "042660", "한화오션", "SELL", 38000, 3000000, "[데모] 시초가 익절")
    except Exception as e:
        logging.warning(f"Demo seed failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 데모 모드(키 없음)는 실데이터(trades.db)와 분리된 demo_trades.db 사용 → 무오염
    demo_mode = not os.getenv("KIS_APP_KEY")
    if demo_mode and os.getenv("DB_PATH") is None:
        database.DB_PATH = str(BASE_DIR / "demo_trades.db")
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
        logging.warning("KIS API keys not set — 데모(목업) 모드로 기동")
        init_demo_scheduler(broker)
        await seed_demo_db()
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


@app.get("/api/mode")
async def get_mode():
    return {"demo": is_demo()}


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
        # 데모 모드: 샘플 현재가 사용
        import demo_data
        info = demo_data.get_demo_price(body.ticker)
    else:
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


# ── 교육 커리큘럼 (FR-7) ──────────────────────────────
# 기획서 v1: 6단계 커리큘럼(표3) + Phase 산출물(표5) 기반 점검 항목
CURRICULUM = [
    {"stage": "1단계 기초 세팅", "lectures": "1-1·1-2·1-3", "items": [
        {"key": "s1_screen", "label": "영웅문 화면 2분할 세팅 완료"},
        {"key": "s1_order",  "label": "퀵 주문창·시장가/지정가 설정"},
        {"key": "s1_expect", "label": "예상 등락 메뉴 등록"},
    ]},
    {"stage": "2단계 장 흐름", "lectures": "1-5·1-6·1-7·1-8", "items": [
        {"key": "s2_pre",     "label": "장전 동시호가 독법 이해"},
        {"key": "s2_routine", "label": "아침 20분 예상 등락 루틴 확립"},
    ]},
    {"stage": "3단계 테마주 전략", "lectures": "2·3·5", "items": [
        {"key": "s3_leader",  "label": "대장·부대장 구분 훈련"},
        {"key": "s3_rotate",  "label": "순환매 패턴 이해"},
        {"key": "s3_mock",    "label": "모의 강일지 10건 작성"},
    ]},
    {"stage": "4단계 특수 매매", "lectures": "4-1·4-2·4-3", "items": [
        {"key": "s4_after",   "label": "시간외(보통주·우선주) 전략 이해"},
        {"key": "s4_credit",  "label": "미수거래 리스크(3일 청산) 숙지"},
    ]},
    {"stage": "5단계 리스크 관리", "lectures": "6", "items": [
        {"key": "s5_friday",  "label": "금요일 리스크 대응 숙지"},
        {"key": "s5_cut",     "label": "풀림 즉시 손절 원칙 훈련"},
    ]},
    {"stage": "6단계 실전 일지", "lectures": "실전 라이브", "items": [
        {"key": "s6_live",    "label": "실전 강일지 10건 작성"},
        {"key": "s6_report",  "label": "종합 성과 리포트 작성"},
    ]},
]


@app.get("/api/curriculum")
async def get_curriculum():
    done = await database.get_curriculum_done()
    total = sum(len(s["items"]) for s in CURRICULUM)
    completed = 0
    stages = []
    for s in CURRICULUM:
        items = []
        for it in s["items"]:
            d = done.get(it["key"], False)
            if d:
                completed += 1
            items.append({"key": it["key"], "label": it["label"], "done": d})
        stages.append({"stage": s["stage"], "lectures": s["lectures"], "items": items})
    pct = round(completed / total * 100) if total else 0
    return {"stages": stages, "completed": completed, "total": total, "percent": pct}


class CurriculumToggle(BaseModel):
    item_key: str
    done: bool

@app.post("/api/curriculum/toggle")
async def toggle_curriculum(body: CurriculumToggle):
    valid = {it["key"] for s in CURRICULUM for it in s["items"]}
    if body.item_key not in valid:
        raise HTTPException(status_code=404, detail="알 수 없는 항목")
    await database.set_curriculum_item(body.item_key, body.done)
    return {"ok": True}


# ── 녹취록 전문 검색 ──────────────────────────────────
@app.get("/api/lectures/search")
async def search_lectures(q: str = "", limit: int = 40):
    import glob, os
    q = (q or "").strip()
    if not q:
        return {"query": "", "results": [], "lecture_count": 0}
    base = BASE_DIR.parent  # 07 폴더 (녹취록 위치)
    out = []
    for path in sorted(glob.glob(str(base / "*_transcript.txt"))):
        try:
            text = open(path, encoding="utf-8").read()
        except Exception:
            continue
        low, ql = text.lower(), q.lower()
        if ql not in low:
            continue
        name = os.path.basename(path).replace("_transcript.txt", "")
        snippets, idx, n = [], low.find(ql), 0
        while idx >= 0 and n < 3:
            st, en = max(0, idx - 45), min(len(text), idx + len(q) + 70)
            snip = text[st:en].replace("\n", " ").strip()
            snippets.append(("…" if st > 0 else "") + snip + ("…" if en < len(text) else ""))
            n += 1
            idx = low.find(ql, idx + 1)
        out.append({"lecture": name, "count": low.count(ql), "snippets": snippets})
    out.sort(key=lambda r: r["count"], reverse=True)
    return {"query": q, "results": out[:limit], "lecture_count": len(out)}


# ── 실전 노하우 (플레이북) ────────────────────────────
@app.get("/api/playbook")
async def get_playbook_api():
    import playbook_data
    return playbook_data.get_playbook()


# ── 메인 페이지 ───────────────────────────────────────
@app.get("/")
async def root():
    path = BASE_DIR / "static" / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8800, reload=True)
