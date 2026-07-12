"""The recognizer: pure functions that turn a fund NAME into structured leverage
info. No network here — that lives in discover.py. This split is deliberate so
the parsing logic is unit-testable offline against sample names.

Design principle: we hardcode the *rules* for recognizing leveraged/inverse
ETFs (a small, stable ruleset), never a list of the funds themselves. New
products with recognizable names are picked up automatically.
"""

from __future__ import annotations

import re

# --- the recognizer ruleset (this is what we maintain, not the fund list) ---

# Issuers known for leveraged / inverse products (metadata + a weak signal).
ISSUERS = [
    "direxion", "proshares", "graniteshares", "tradr", "t-rex", "trex",
    "microsectors", "leverage shares", "defiance", "kurv", "axs", "bank of montreal",
]

# Strong leverage markers, matched on WORD boundaries so "bull" doesn't fire on
# "BulletShares". Numeric markers (2x, -3x) are matched separately.
_STRONG = re.compile(r"\b(ultrapro|ultrashort|ultra|bull|bear|inverse|leveraged)\b")
_NUM = re.compile(r"-?\d+(?:\.\d+)?x\b")
_SHORT = re.compile(r"\bshort\b")

# Uppercase tokens that look like tickers but never are, in fund names.
# Includes issuer tokens (e.g. REX from "T-REX") so the issuer name isn't
# mistaken for the underlying.
TICKER_STOPWORDS = {
    "ETF", "ETN", "US", "USD", "II", "III", "IV", "AM", "PM", "DR", "ADR",
    "MSCI", "FTSE", "REIT", "AI", "REX",
}


def detect_issuer(name: str) -> str | None:
    low = name.lower()
    for iss in ISSUERS:
        if iss in low:
            return iss.title()
    return None


def is_leveraged(name: str) -> bool:
    low = name.lower()
    if _STRONG.search(low) or _NUM.search(low):
        return True
    # bare 'short' (no number, e.g. "ProShares Short S&P500") is only an inverse
    # marker when a known leverage issuer makes it — guards against "iShares
    # Short Treasury" style short-duration bond funds.
    return bool(_SHORT.search(low)) and detect_issuer(name) is not None


def parse_leverage(name: str) -> tuple[float | None, str | None]:
    """Return (signed_factor, direction). direction is 'long' | 'short' | None.

    e.g. 'Direxion Daily NVDA Bull 2X Shares' -> (2.0, 'long')
         'ProShares UltraShort QQQ'           -> (-2.0, 'short')
         'ProShares Short S&P500'             -> (-1.0, 'short')
    """
    low = name.lower()

    # direction — check the compound word 'ultrashort' before bare 'short'/'ultra'
    if "ultrashort" in low:
        direction = "short"
    elif any(w in low for w in ("bear", "inverse")) or re.search(r"-[123](?:\.\d+)?x", low):
        direction = "short"
    elif re.search(r"\bshort\b", low):
        direction = "short"
    elif any(w in low for w in ("bull", "ultra", "long")) or re.search(r"\b\d+(?:\.\d+)?x\b", low):
        direction = "long"
    else:
        direction = None

    # magnitude
    if "ultrapro" in low:
        mag = 3.0
    elif "ultrashort" in low or "ultra" in low:
        mag = 2.0
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*x", low)
        if m:
            mag = float(m.group(1))
        elif direction == "short":  # bare 'short'/'inverse' with no number = -1x
            mag = 1.0
        else:
            mag = None

    if mag is None or direction is None:
        return (None, direction)
    factor = -mag if direction == "short" else mag
    return (factor, direction)


def parse_underlying(name: str, valid_tickers: set[str],
                     etf_tickers: set[str]) -> tuple[str | None, str]:
    """Find the underlying ticker in the name and classify the tier.

    Returns (underlying_or_None, tier). tier is one of:
      'single_stock' | 'index_or_etf' | 'sector_thematic'
    A validated 2+ letter uppercase token wins; single letters are treated as
    noise (e.g. the 'S'/'P' in 'S&P500') to avoid false positives.
    """
    tokens = re.findall(r"\b[A-Z]{2,5}\b", name)
    for t in tokens:
        if t in TICKER_STOPWORDS:
            continue
        if t in valid_tickers:
            tier = "index_or_etf" if t in etf_tickers else "single_stock"
            return (t, tier)
    return (None, "sector_thematic")


def confidence(factor: float | None, direction: str | None,
               underlying: str | None, tier: str) -> str:
    """high: leverage fully parsed AND a ticker underlying validated.
    medium: leverage parsed but underlying is sector/thematic (expected).
    low: couldn't pin down factor or direction."""
    if factor is None or direction is None:
        return "low"
    if underlying is not None:
        return "high"
    return "medium"


def build_record(ticker: str, name: str, valid_tickers: set[str],
                 etf_tickers: set[str]) -> dict | None:
    """Full recognizer pass for one fund. Returns None if not leveraged/inverse."""
    if not is_leveraged(name):
        return None
    factor, direction = parse_leverage(name)
    underlying, tier = parse_underlying(name, valid_tickers, etf_tickers)
    return {
        "ticker": ticker,
        "name": name,
        "issuer": detect_issuer(name),
        "factor": factor,
        "direction": direction,
        "underlying": underlying,
        "tier": tier,
        "confidence": confidence(factor, direction, underlying, tier),
    }
