"""Enrich letf_universe.json with average daily dollar volume.

Why grouped-daily: one call returns OHLCV for EVERY US ticker on a date, so
N days of liquidity for the whole universe costs N calls (not one per fund).
Avg $ volume is the tradability signal a swing trader ranks by — a 2x fund
doing $2B/day and one doing $200K/day are not interchangeable.

Usage: python -m letf.enrich [--days 10]
Writes adv_usd (int, may be None) + adv_days into each universe record.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from letf.discover import BASE, DATA, _key


def _grouped(day: date) -> dict[str, tuple[float, float]]:
    """ticker -> (close, volume) for one date; {} on non-trading days. Cached."""
    cache = DATA / f"_grouped_{day.isoformat()}.json"
    if cache.exists():
        return {k: tuple(v) for k, v in json.loads(cache.read_text()).items()}
    headers = {"Authorization": f"Bearer {_key()}"}
    url = f"{BASE}/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}"
    for attempt in range(5):
        r = requests.get(url, params={"adjusted": "true"}, headers=headers,
                         timeout=60)
        if r.status_code == 429:
            time.sleep(15)
            continue
        r.raise_for_status()
        break
    else:
        raise RuntimeError("persistent 429s from Polygon; giving up")
    results = r.json().get("results") or []
    out = {row["T"]: (row["c"], row["v"]) for row in results
           if row.get("c") and row.get("v")}
    cache.write_text(json.dumps(out))
    return out


def recent_trading_days(n: int) -> list[dict[str, tuple[float, float]]]:
    """Grouped bars for the last n trading days (skips weekends/holidays)."""
    days, cursor, misses = [], date.today() - timedelta(days=1), 0
    while len(days) < n and misses < 10:
        bars = _grouped(cursor)
        if bars:
            days.append(bars)
            print(f"  {cursor}: {len(bars):,} tickers")
        else:
            misses += 1
        cursor -= timedelta(days=1)
        time.sleep(13)  # free-tier pacing
    return days


def compute_adv(day_maps: list[dict[str, tuple[float, float]]],
                tickers: set[str]) -> dict[str, int | None]:
    """Average close*volume per ticker over the days it actually traded.

    Pure function — offline-testable. None = never seen (no liquidity data).
    """
    out: dict[str, int | None] = {}
    for t in tickers:
        dollars = [c * v for bars in day_maps
                   if (cv := bars.get(t)) for c, v in [cv]]
        out[t] = round(sum(dollars) / len(dollars)) if dollars else None
    return out


def enrich(days: int = 10) -> dict:
    path = DATA / "letf_universe.json"
    universe = json.loads(path.read_text())
    tickers = {r["ticker"] for r in universe["records"]}
    day_maps = recent_trading_days(days)
    adv = compute_adv(day_maps, tickers)
    for r in universe["records"]:
        r["adv_usd"] = adv.get(r["ticker"])
        r["adv_days"] = days
    universe["enriched"] = date.today().isoformat()
    path.write_text(json.dumps(universe, indent=2))
    covered = sum(1 for v in adv.values() if v is not None)
    print(f"\nliquidity attached: {covered}/{len(tickers)} funds "
          f"over {len(day_maps)} trading days")
    return universe


def main() -> int:
    days = 10
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    enrich(days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
