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
