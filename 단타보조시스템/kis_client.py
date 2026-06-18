import httpx
import json
import os
import time
from pathlib import Path

TOKEN_CACHE = ".token_cache"

REAL_BASE = "https://openapi.koreainvestment.com:9443"
MOCK_BASE = "https://openapivts.koreainvestment.com:9443"
REAL_WS   = "wss://ops.koreainvestment.com:21000"
MOCK_WS   = "wss://openapivts.koreainvestment.com:31000"


class KISClient:
    def __init__(self, app_key: str, app_secret: str, account_no: str, mock: bool = False):
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no
        self.mock = mock
        self.base_url = MOCK_BASE if mock else REAL_BASE
        self.ws_url = MOCK_WS if mock else REAL_WS
        self._token: str | None = None
        self._token_expires: float = 0

    async def _fetch_token(self) -> str:
        async with httpx.AsyncClient() as c:
            resp = await c.post(
                f"{self.base_url}/oauth2/tokenP",
                json={"grant_type": "client_credentials",
                      "appkey": self.app_key,
                      "appsecret": self.app_secret},
                headers={"content-type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def _get_token(self) -> str:
        cache = Path(TOKEN_CACHE)
        try:
            if cache.exists():
                data = json.loads(cache.read_text())
                if time.time() < data.get("expires", 0):
                    return data["token"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass
        token = await self._fetch_token()
        self._token = token
        try:
            cache.write_text(json.dumps({"token": token, "expires": time.time() + 86000}))
        except OSError:
            pass
        return token

    def _headers(self, tr_id: str, token: str) -> dict:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    async def get_ranking(self, market: str = "J") -> list[dict]:
        """시장별 등락률 상위 30종목 반환. market: J=코스피 Q=코스닥"""
        token = self._token or await self._get_token()
        params = {
            "fid_cond_mrkt_div_code": market,
            "fid_cond_scr_div_code": "20171",
            "fid_input_iscd": "0000",
            "fid_rank_sort_cls_code": "0",
            "fid_input_cnt_1": "0",
            "fid_prc_cls_code": "1",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0",
            "fid_rsfl_rate1": "",
            "fid_rsfl_rate2": "",
        }
        async with httpx.AsyncClient() as c:
            resp = await c.get(
                f"{self.base_url}/uapi/domestic-stock/v1/ranking/fluctuation",
                headers=self._headers("FHPST01700000", token),
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("output", [])
        result = []
        for it in items:
            prev_vol = int(it.get("prdy_vol") or 1)
            curr_vol = int(it.get("acml_vol") or 0)
            result.append({
                "ticker":       it["stck_shrn_iscd"],
                "name":         it["hts_kor_isnm"],
                "rank":         int(it["data_rank"]),
                "price":        int(it["stck_prpr"]),
                "change_rate":  float(it["prdy_ctrt"]),
                "volume":       curr_vol,
                "volume_ratio": round(curr_vol / prev_vol, 2) if prev_vol else 0,
                "market_cap":   int(it.get("stck_mktc", 0)),
                "market":       market,
            })
        return result

    async def get_ws_approval_key(self) -> str:
        """WebSocket 접속 승인키 발급"""
        async with httpx.AsyncClient() as c:
            resp = await c.post(
                f"{self.base_url}/oauth2/Approval",
                json={"grant_type": "client_credentials",
                      "appkey": self.app_key,
                      "secretkey": self.app_secret},
                headers={"content-type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()["approval_key"]

    async def get_price(self, ticker: str) -> dict:
        """종목 현재가·시가총액·등락률 반환"""
        token = self._token or await self._get_token()
        async with httpx.AsyncClient() as c:
            resp = await c.get(
                f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=self._headers("FHKST01010100", token),
                params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker},
                timeout=10,
            )
            resp.raise_for_status()
            out = resp.json().get("output", {})
        prev_vol = int(out.get("prdy_vol") or 1)
        curr_vol = int(out.get("acml_vol") or 0)
        prev_price = int(out.get("prdy_clpr") or 1)
        return {
            "ticker":       ticker,
            "price":        int(out.get("stck_prpr", 0)),
            "change_rate":  float(out.get("prdy_ctrt", 0)),
            "volume":       curr_vol,
            "volume_ratio": round(curr_vol / prev_vol, 2) if prev_vol else 0,
            "market_cap":   int(out.get("hts_avls", 0)),
            "prev_price":   prev_price,
        }


def create_client_from_env() -> "KISClient":
    return KISClient(
        app_key=os.environ["KIS_APP_KEY"],
        app_secret=os.environ["KIS_APP_SECRET"],
        account_no=os.environ["KIS_ACCOUNT_NO"],
        mock=os.getenv("KIS_MOCK", "false").lower() == "true",
    )
