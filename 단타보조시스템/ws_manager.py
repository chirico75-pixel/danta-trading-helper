import asyncio
import json
import logging
import websockets

logger = logging.getLogger(__name__)

class WSManager:
    def __init__(self, ws_url: str, approval_key: str, broker):
        self.ws_url = ws_url
        self.approval_key = approval_key
        self.broker = broker
        self._subscriptions: set[str] = set()
        self._ws = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        ws = self._ws
        if ws is not None:
            await ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def subscribe(self, ticker: str):
        self._subscriptions.add(ticker)
        if self._ws:
            await self._send_subscribe(ticker)

    async def unsubscribe(self, ticker: str):
        self._subscriptions.discard(ticker)
        if self._ws:
            await self._send_unsubscribe(ticker)

    async def _send_subscribe(self, ticker: str):
        msg = json.dumps({
            "header": {"approval_key": self.approval_key,
                       "custtype": "P", "tr_type": "1",
                       "content-type": "utf-8"},
            "body": {"input": {"tr_id": "H0STCNT0", "tr_key": ticker}}
        })
        await self._ws.send(msg)

    async def _send_unsubscribe(self, ticker: str):
        msg = json.dumps({
            "header": {"approval_key": self.approval_key,
                       "custtype": "P", "tr_type": "2",
                       "content-type": "utf-8"},
            "body": {"input": {"tr_id": "H0STCNT0", "tr_key": ticker}}
        })
        await self._ws.send(msg)

    async def _run_loop(self):
        while self._running:
            try:
                async with websockets.connect(self.ws_url, ping_interval=30) as ws:
                    self._ws = ws
                    logger.info("KIS WebSocket connected")
                    for ticker in list(self._subscriptions):
                        await self._send_subscribe(ticker)
                    async for raw in ws:
                        await self._handle(raw)
            except asyncio.CancelledError:
                logger.info("WSManager loop cancelled")
                break
            except Exception as e:
                self._ws = None
                if self._running:
                    logger.warning(f"WebSocket disconnected: {e}. Reconnecting in 5s...")
                    await self.broker.broadcast("ws_status", {"status": "reconnecting"})
                    await asyncio.sleep(5)
        self._ws = None

    async def _handle(self, raw: str):
        if raw.startswith("{"):
            return
        parts = raw.split("|")
        if len(parts) < 4:
            return
        tr_id = parts[1]
        if tr_id != "H0STCNT0":
            return
        fields = parts[3].split("^")
        if len(fields) < 13:
            return
        ticker = fields[0]
        try:
            price = int(fields[2])
            change_rate = float(fields[5]) if fields[5] else 0.0
        except (ValueError, IndexError):
            logger.warning(f"Failed to parse price fields: {fields[:6]}")
            return
        await self.broker.broadcast("price_update", {
            "ticker": ticker,
            "price": price,
            "change_rate": change_rate,
        })
