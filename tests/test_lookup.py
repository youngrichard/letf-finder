"""Offline test for lookup() — feeds a fake universe, no network."""

from letf import lookup

UNIVERSE = {
    "records": [
        {"ticker": "NVDL", "name": "GraniteShares 2x Long NVDA Daily ETF",
         "factor": 2.0, "direction": "long", "underlying": "NVDA",
         "tier": "single_stock", "confidence": "high"},
        {"ticker": "NVD", "name": "GraniteShares 2x Short NVDA Daily ETF",
         "factor": -2.0, "direction": "short", "underlying": "NVDA",
         "tier": "single_stock", "confidence": "high"},
        {"ticker": "TQQQ", "name": "ProShares UltraPro QQQ",
         "factor": 3.0, "direction": "long", "underlying": "QQQ",
         "tier": "index_or_etf", "confidence": "high"},
        {"ticker": "TSLL", "name": "Direxion Daily TSLA Bull 2X Shares",
         "factor": 2.0, "direction": "long", "underlying": "TSLA",
         "tier": "single_stock", "confidence": "high"},
    ]
}


def test_lookup_returns_direct_matches():
    res = lookup.lookup("NVDA", UNIVERSE)
    tickers = [e["ticker"] for e in res["direct"]]
    assert set(tickers) == {"NVDL", "NVD"}
    assert res["index"] == []
    # long ranked before short
    assert res["direct"][0]["ticker"] == "NVDL"


def test_lookup_index_tier():
    res = lookup.lookup("QQQ", UNIVERSE)
    assert [e["ticker"] for e in res["index"]] == ["TQQQ"]
    assert res["direct"] == []


def test_lookup_is_case_insensitive():
    assert lookup.lookup("tsla", UNIVERSE)["direct"][0]["ticker"] == "TSLL"


def test_caveat_always_present():
    res = lookup.lookup("NVDA", UNIVERSE)
    assert "daily" in res["caveat"].lower()


def test_no_match_returns_empty():
    res = lookup.lookup("AAPL", UNIVERSE)
    assert res["direct"] == [] and res["index"] == []
