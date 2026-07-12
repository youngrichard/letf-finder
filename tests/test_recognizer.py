"""Offline tests for the recognizer — real fund-name patterns, no network.

This proves the parsing logic before any Polygon call is made. The live
discover.py just feeds real names into these same functions.
"""

from letf import recognizer as r

# small fake validation universe
VALID = {"NVDA", "TSLA", "AAPL", "QQQ", "SPY", "IWM", "SOXX"}
ETFS = {"QQQ", "SPY", "IWM", "SOXX"}


def rec(name, ticker="XXXX"):
    return r.build_record(ticker, name, VALID, ETFS)


def test_single_stock_bull_2x():
    d = rec("Direxion Daily NVDA Bull 2X Shares")
    assert d["factor"] == 2.0 and d["direction"] == "long"
    assert d["underlying"] == "NVDA" and d["tier"] == "single_stock"
    assert d["confidence"] == "high"


def test_single_stock_graniteshares_form():
    d = rec("GraniteShares 2x Long NVDA Daily ETF")
    assert d["factor"] == 2.0 and d["underlying"] == "NVDA"
    assert d["issuer"] == "Graniteshares"


def test_single_stock_bear_1x():
    d = rec("Direxion Daily TSLA Bear 1X Shares")
    assert d["factor"] == -1.0 and d["direction"] == "short"
    assert d["underlying"] == "TSLA" and d["tier"] == "single_stock"


def test_ultrapro_index_is_3x():
    d = rec("ProShares UltraPro QQQ")
    assert d["factor"] == 3.0 and d["direction"] == "long"
    assert d["underlying"] == "QQQ" and d["tier"] == "index_or_etf"


def test_ultrashort_is_negative_2x():
    d = rec("ProShares UltraShort QQQ")
    assert d["factor"] == -2.0 and d["direction"] == "short"
    assert d["underlying"] == "QQQ"


def test_ultra_alone_is_2x():
    d = rec("ProShares Ultra S&P500")  # 'Ultra' (not UltraPro) = 2x
    assert d["factor"] == 2.0 and d["direction"] == "long"


def test_bare_short_is_negative_1x():
    d = rec("ProShares Short S&P500")
    assert d["factor"] == -1.0 and d["direction"] == "short"
    # 'S&P500' has no valid ticker token -> sector/thematic, needs a map (Phase 2)
    assert d["underlying"] is None and d["tier"] == "sector_thematic"
    assert d["confidence"] == "medium"


def test_sector_thematic_no_ticker():
    d = rec("Direxion Daily Semiconductor Bull 3X Shares")
    assert d["factor"] == 3.0 and d["direction"] == "long"
    assert d["underlying"] is None and d["tier"] == "sector_thematic"


def test_single_letter_not_mistaken_for_ticker():
    # the 'S' and 'P' in S&P must not be picked up as underlyings
    d = rec("ProShares UltraPro Short S&P 500")
    assert d["underlying"] is None


def test_non_leveraged_fund_is_skipped():
    assert rec("Vanguard Total Stock Market ETF") is None
    assert rec("SPDR S&P 500 ETF Trust") is None


def test_index_underlying_classified_as_etf_tier():
    d = rec("Direxion Daily Semiconductor Bull 3X SOXX")  # SOXX is an ETF here
    assert d["underlying"] == "SOXX" and d["tier"] == "index_or_etf"


def test_low_confidence_when_factor_unparseable():
    # leveraged marker present (issuer + 'leveraged') but no clear factor/direction
    d = rec("Some Direxion Leveraged Product")
    assert d is not None
    assert d["confidence"] == "low"


def test_bulletshares_not_flagged_leveraged():
    # 'bull' must match on a word boundary — BulletShares bond ETFs are not leveraged
    assert rec("Invesco BulletShares 2036 Corporate Bond ETF") is None


def test_issuer_token_rex_not_mistaken_for_underlying():
    # 'T-REX' issuer token must not shadow the real underlying (NVDA)
    d = r.build_record("XXXX", "T-REX 2X Long NVDA Daily Target ETF",
                       VALID | {"REX"}, ETFS)
    assert d["underlying"] == "NVDA"
