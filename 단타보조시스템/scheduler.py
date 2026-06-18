import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()
_kis = None
_broker = None
_ranking_cache: dict = {"J": [], "Q": []}


def init_scheduler(kis_client, sse_broker):
    global _kis, _broker
    if _scheduler.running:
        return
    _kis = kis_client
    _broker = sse_broker
    _scheduler.add_job(_poll_ranking, "interval", seconds=5, id="ranking_poll",
                       misfire_grace_time=3)
    _scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


async def _poll_ranking():
    now = datetime.now()
    if now.weekday() >= 5:
        return
    if not (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 30)):
        return
    try:
        for market in ("J", "Q"):
            items = await _kis.get_ranking(market)
            _ranking_cache[market] = items
        combined = sorted(
            _ranking_cache["J"] + _ranking_cache["Q"],
            key=lambda x: x["change_rate"], reverse=True
        )
        await _broker.broadcast("ranking", {
            "J": _ranking_cache["J"][:30],
            "Q": _ranking_cache["Q"][:30],
            "ALL": combined[:30],
        })
    except Exception as e:
        logger.warning(f"Ranking poll failed: {e}")


def get_cached_ranking(market: str = "ALL") -> list:
    if market == "ALL":
        combined = sorted(
            _ranking_cache["J"] + _ranking_cache["Q"],
            key=lambda x: x["change_rate"], reverse=True
        )
        return combined[:30]
    return _ranking_cache.get(market, [])


# ── 데모(목업) 모드 ────────────────────────────────────
# KIS 키 미설정 시, 샘플 시세를 5초마다 브로드캐스트해 UI를 체험 가능하게 함.
_demo_on = False


def init_demo_scheduler(sse_broker):
    """데모 랭킹/관심종목 시세를 주기 브로드캐스트 (실데이터 경로와 분리)"""
    global _broker, _demo_on
    _broker = sse_broker
    _demo_on = True
    import demo_data
    seed = demo_data.get_demo_ranking()
    _ranking_cache["J"] = seed["J"]
    _ranking_cache["Q"] = seed["Q"]
    if not _scheduler.running:
        _scheduler.start()
    _scheduler.add_job(_broadcast_demo, "interval", seconds=5, id="demo_ranking",
                       misfire_grace_time=3, replace_existing=True)
    logger.info("Demo scheduler started (KIS keys not set)")


async def _broadcast_demo():
    import demo_data
    seed = demo_data.get_demo_ranking()
    _ranking_cache["J"] = seed["J"]
    _ranking_cache["Q"] = seed["Q"]
    combined = sorted(seed["J"] + seed["Q"], key=lambda x: x["change_rate"], reverse=True)
    await _broker.broadcast("ranking", {"J": seed["J"][:30], "Q": seed["Q"][:30], "ALL": combined[:30]})
    # 관심종목 실시간 시세(데모)
    try:
        import database
        for item in await database.get_watchlist():
            px = demo_data.get_demo_price(item["ticker"])
            await _broker.broadcast("price_update", {
                "ticker": item["ticker"], "price": px["price"], "change_rate": px["change_rate"]})
    except Exception as e:
        logger.warning(f"Demo watchlist broadcast failed: {e}")


def is_demo() -> bool:
    return _demo_on
