"""The recognizer: pure functions that turn a fund NAME into structured leverage
info. No network here — that lives in discover.py. This split is deliberate so
the parsing logic is unit-testable offline against sample names.

Design principle: we hardcode the *rules* for recognizing leveraged/inverse
ETFs (a small, stable ruleset), never a list of the funds themselves. New
products with recognizable names are picked up automatically.

All name-reading happens in ONE pass (`parse_name`); `is_leveraged` and
`parse_leverage` are derived views of it, so the marker grammar cannot drift
between two implementations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- the recognizer ruleset (this is what we maintain, not the fund list) ---

# Issuers known for leveraged / inverse products, matched on word boundaries.
ISSUERS = [
    "direxion", "proshares", "graniteshares", "tradr", "t-rex",
    "microsectors", "leverage shares", "defiance", "kurv", "axs",
    "bank of montreal", "rex shares",
]
_ISSUER_RE = re.compile(r"\b(" + "|".join(re.escape(i) for i in ISSUERS) + r")\b")

# One grammar for the whole module.
_NUMX = re.compile(r"(-?\d+(?:\.\d+)?)\s*x\b")          # 2x, 1.5X, -3x, "2 X"
_UNAMBIGUOUS = re.compile(r"\b(ultrapro|ultrashort|ultra|inverse)\b")
_AMBIGUOUS = re.compile(r"\b(bull|bear|leveraged)\b")   # need a number or issuer
_SHORT = re.compile(r"\bshort\b")
_LONG = re.compile(r"\b(bull|long)\b")
_BEARISH = re.compile(r"\b(bear|inverse)\b")

# Names these phrases appear in are asset classes / strategies, not daily
# leveraged funds — hard excludes.
EXCLUDE_PHRASES = ("leveraged loan",)

# Issuer brand tokens stripped from the name BEFORE ticker scanning, so the
# brand isn't mistaken for the underlying (T-REX funds parsed as ticker REX).
# Evidence: leveraged fund names always carry the hyphenated form.
_STRIP_BRANDS = re.compile(r"\bT-REX\b", re.I)

# Uppercase tokens that look like tickers but never are, in fund names.
# AXS / MAX are issuer brand tokens (AXS funds, MicroSectors MAX ETNs); the
# collision cost is that Axis Capital (AXS) / MediaAlpha (MAX) can't be
# underlyings — accepted: no single-stock LETF exists on either.
TICKER_STOPWORDS = {
    "ETF", "ETN", "US", "USD", "II", "III", "IV", "AM", "PM", "DR", "ADR",
    "MSCI", "FTSE", "REIT", "AI", "AXS", "MAX",
}


@dataclass(frozen=True)
class NameParse:
    """Everything the name alone tells us, from a single pass."""
    marked: bool                 # is this a leveraged/inverse product at all?
    factor: float | None         # signed, e.g. 2.0 / -1.5 / None if unparsed
    direction: str | None        # 'long' | 'short' | None
    issuer: str | None


def parse_name(name: str) -> NameParse:
    low = name.lower()
    issuer_m = _ISSUER_RE.search(low)
    issuer = issuer_m.group(1).title() if issuer_m else None

    if any(p in low for p in EXCLUDE_PHRASES):
        return NameParse(False, None, None, issuer)

    num = _NUMX.search(low)
    # Marked if: a numeric factor, an unambiguous word, an ambiguous word
    # backed by a number or a known issuer, or bare 'short' from a known
    # issuer ("ProShares Short S&P500"; guards against short-duration bond
    # funds and "Bull Hedge"-style strategy products from unknown issuers).
    marked = bool(
        num
        or _UNAMBIGUOUS.search(low)
        or (_AMBIGUOUS.search(low) and (num or issuer))
        or (_SHORT.search(low) and issuer)
    )
    if not marked:
        return NameParse(False, None, None, issuer)

    # direction — compound 'ultrashort' first, then bearish words / negative
    # number, then bare short, then bullish words / positive number
    if "ultrashort" in low:
        direction = "short"
    elif _BEARISH.search(low) or (num and num.group(1).startswith("-")):
        direction = "short"
    elif _SHORT.search(low):
        direction = "short"
    elif _LONG.search(low) or "ultra" in low or num:
        direction = "long"
    else:
        direction = None

    # magnitude
    if "ultrapro" in low:
        mag = 3.0
    elif "ultrashort" in low or "ultra" in low:
        mag = 2.0
    elif num:
        mag = abs(float(num.group(1)))
    elif direction == "short":   # bare 'short'/'inverse', no number = -1x
        mag = 1.0
    else:
        mag = None

    if mag is None or direction is None:
        return NameParse(True, None, direction, issuer)
    return NameParse(True, -mag if direction == "short" else mag, direction, issuer)


# --- thin public views, kept for API stability ---

def is_leveraged(name: str) -> bool:
    return parse_name(name).marked


def parse_leverage(name: str) -> tuple[float | None, str | None]:
    p = parse_name(name)
    return (p.factor, p.direction)


def detect_issuer(name: str) -> str | None:
    return parse_name(name).issuer


def parse_underlying(name: str, valid_tickers: set[str],
                     etf_tickers: set[str]) -> tuple[str | None, str]:
    """Find the underlying ticker in the name and classify the tier.

    Returns (underlying_or_None, tier). tier is one of:
      'single_stock' | 'index_or_etf' | 'sector_thematic'
    Issuer brand tokens are stripped first so they can't shadow the real
    underlying; a validated 2-5 letter uppercase token wins; single letters
    are noise (the 'S'/'P' in 'S&P500').
    """
    cleaned = _STRIP_BRANDS.sub(" ", name)
    for t in re.findall(r"\b[A-Z]{2,5}\b", cleaned):
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
    p = parse_name(name)
    if not p.marked:
        return None
    underlying, tier = parse_underlying(name, valid_tickers, etf_tickers)
    return {
        "ticker": ticker,
        "name": name,
        "issuer": p.issuer,
        "factor": p.factor,
        "direction": p.direction,
        "underlying": underlying,
        "tier": tier,
        "confidence": confidence(p.factor, p.direction, underlying, tier),
    }
