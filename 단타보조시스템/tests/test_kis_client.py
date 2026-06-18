import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from kis_client import KISClient

@pytest.fixture
def client():
    return KISClient(app_key="test_key", app_secret="test_secret", account_no="12345678-01", mock=True)

@pytest.mark.asyncio
async def test_get_token_calls_api(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "abc123", "token_type": "Bearer"}
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        token = await client._fetch_token()
    assert token == "abc123"

@pytest.mark.asyncio
async def test_get_ranking_returns_list(client):
    client._token = "test_token"
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "output": [
            {"stck_shrn_iscd": "005930", "hts_kor_isnm": "삼성전자",
             "data_rank": "1", "stck_prpr": "75000", "prdy_ctrt": "28.50",
             "acml_vol": "10000000", "prdy_vol": "3000000", "stck_mktc": "5000000000000"}
        ]
    }
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_ranking("J")
    assert len(result) == 1
    assert result[0]["ticker"] == "005930"
    assert result[0]["change_rate"] == 28.50
    assert result[0]["volume_ratio"] == pytest.approx(3.33, abs=0.1)

@pytest.mark.asyncio
async def test_get_price_returns_dict(client):
    client._token = "test_token"
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "output": {
            "stck_prpr": "75000",
            "prdy_ctrt": "5.20",
            "acml_vol": "10000000",
            "prdy_vol": "3000000",
            "hts_avls": "4500000",
            "prdy_clpr": "71300"
        }
    }
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_price("005930")
    assert result["price"] == 75000
    assert result["market_cap"] == 4500000
