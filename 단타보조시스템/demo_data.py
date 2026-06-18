# -*- coding: utf-8 -*-
"""
데모(목업) 데이터 — KIS API 키 없이 프로그램을 체험할 수 있게 하는 샘플 시세.
실제 거래 데이터가 아님. 키 미설정 시에만 사용됨(실데이터 경로와 분리).
"""
import random

# 코스피(J)·코스닥(Q) 샘플 급등주 (테마주 단타 데모용)
_BASE = {
    "J": [
        {"ticker": "042660", "name": "한화오션",   "price": 38250, "change_rate": 24.8, "market_cap": 117000},
        {"ticker": "010140", "name": "삼성중공업", "price": 12880, "change_rate": 19.6, "market_cap": 95000},
        {"ticker": "267250", "name": "HD현대",     "price": 71500, "change_rate": 15.2, "market_cap": 62000},
        {"ticker": "047810", "name": "한국항공우주","price": 58900, "change_rate": 12.4, "market_cap": 57000},
        {"ticker": "012450", "name": "한화에어로",  "price": 248000,"change_rate": 9.8,  "market_cap": 124000},
        {"ticker": "079550", "name": "LIG넥스원",  "price": 211500,"change_rate": 7.1,  "market_cap": 46000},
        {"ticker": "088350", "name": "한화생명",    "price": 3120,  "change_rate": 5.3,  "market_cap": 27000},
        {"ticker": "003490", "name": "대한항공",    "price": 22650, "change_rate": 3.9,  "market_cap": 83000},
    ],
    "Q": [
        {"ticker": "247540", "name": "에코프로비엠","price": 138900,"change_rate": 28.6, "market_cap": 90000},
        {"ticker": "086520", "name": "에코프로",    "price": 98700, "change_rate": 22.1, "market_cap": 80000},
        {"ticker": "091990", "name": "셀트리온헬스","price": 41200, "change_rate": 17.3, "market_cap": 64000},
        {"ticker": "196170", "name": "알테오젠",    "price": 312000,"change_rate": 13.5, "market_cap": 88000},
        {"ticker": "035900", "name": "JYP Ent.",   "price": 68400, "change_rate": 10.2, "market_cap": 24000},
        {"ticker": "263750", "name": "펄어비스",    "price": 39850, "change_rate": 8.4,  "market_cap": 22000},
        {"ticker": "293490", "name": "카카오게임즈","price": 19980, "change_rate": 6.0,  "market_cap": 17000},
        {"ticker": "112040", "name": "위메이드",    "price": 41250, "change_rate": 4.2,  "market_cap": 14000},
    ],
}


def _jitter(items):
    out = []
    for i, b in enumerate(items):
        dr = round(b["change_rate"] + random.uniform(-0.6, 0.6), 2)
        price = int(b["price"] * (1 + random.uniform(-0.004, 0.004)))
        vr = round(random.uniform(1.5, 6.5), 2)
        out.append({
            "ticker": b["ticker"],
            "name": b["name"],
            "rank": i + 1,
            "price": price,
            "change_rate": dr,
            "volume": int(random.uniform(1_000_000, 30_000_000)),
            "volume_ratio": vr,
            "market_cap": b["market_cap"],
            "market": "DEMO",
        })
    out.sort(key=lambda x: x["change_rate"], reverse=True)
    for i, o in enumerate(out):
        o["rank"] = i + 1
    return out


def get_demo_ranking() -> dict:
    """{'J':[...], 'Q':[...]} 형태의 지터 적용 샘플 랭킹 반환"""
    return {"J": _jitter(_BASE["J"]), "Q": _jitter(_BASE["Q"])}


def get_demo_price(ticker: str) -> dict:
    """체크리스트/관심종목용 샘플 현재가. 알 수 없는 종목도 합성 생성."""
    for mkt in ("J", "Q"):
        for b in _BASE[mkt]:
            if b["ticker"] == ticker:
                price = int(b["price"] * (1 + random.uniform(-0.004, 0.004)))
                return {
                    "ticker": ticker,
                    "price": price,
                    "change_rate": round(b["change_rate"] + random.uniform(-0.6, 0.6), 2),
                    "volume": int(random.uniform(1_000_000, 30_000_000)),
                    "volume_ratio": round(random.uniform(2.0, 6.0), 2),
                    "market_cap": b["market_cap"],
                    "prev_price": int(price / (1 + b["change_rate"] / 100)),
                }
    # 미등록 종목: 합성 데이터
    price = random.randint(3000, 90000)
    cr = round(random.uniform(-5, 25), 2)
    return {
        "ticker": ticker,
        "price": price,
        "change_rate": cr,
        "volume": int(random.uniform(500_000, 20_000_000)),
        "volume_ratio": round(random.uniform(0.8, 5.0), 2),
        "market_cap": random.randint(5000, 120000),
        "prev_price": int(price / (1 + cr / 100)),
    }
