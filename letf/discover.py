"""Discover the leveraged/inverse fund universe from Polygon and write it to
data/letf_universe.json. Regenerate daily; new launches appear, closures drop.

Pulls three lists from /v3/reference/tickers:
  - all active ETFs + ETNs -> the candidate pool (leveraged products ship under
    both wrappers — MicroSectors-style notes are ETNs, not ETFs)
  - all active stocks      -> the set we validate parsed underlyings against
Then runs the (offline-tested) recognizer over the candidate names.

Needs POLYGON_API_KEY in .env or the environment. Free tier (5 req/min) works;
the full pull is ~10 pages, so it paces itself. Raw pulls are cached so re-runs
are cheap; pass --refresh to force a re-fetch.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

from letf import recognizer

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://api.polygon.io"


def _key() -> str:
    import os
    if os.environ.get("POLYGON_API_KEY"):
        return os.environ["POLYGON_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("POLYGON_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("POLYGON_API_KEY not set (in environment or .env)")


def _fetch_all(ticker_type: str, cache: Path, refresh: bool) -> list[dict]:
    """Page through /v3/reference/tickers for one type; cache the full list.

    Auth is a Bearer header, never a query param — keys in URLs leak into
    exception messages, logs, and proxies; keys in headers don't.
    """
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
    headers = {"Authorization": f"Bearer {_key()}"}
    out, url = [], f"{BASE}/v3/reference/tickers"
    params = {"type": ticker_type, "market": "stocks", "active": "true",
              "limit": 1000}
    page = rate_limited = 0
    while True:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code == 429:
            rate_limited += 1
            if rate_limited > 30:  # don't hang unattended runs forever
                raise RuntimeError("persistent 429s from Polygon; giving up")
            time.sleep(15)
            continue
        r.raise_for_status()
        body = r.json()
        out.extend(body.get("results", []))
        page += 1
        print(f"  {ticker_type}: page {page}, {len(out)} so far")
        nxt = body.get("next_url")
        if not nxt:
            break
        url, params = nxt, None  # next_url carries the cursor; auth stays in header
        time.sleep(13)  # free-tier pacing (5/min)
    cache.write_text(json.dumps(out))
    return out


def discover(refresh: bool = False) -> dict:
    DATA.mkdir(exist_ok=True)
    candidates = (_fetch_all("ETF", DATA / "_etfs.json", refresh)
                  + _fetch_all("ETN", DATA / "_etns.json", refresh))
    stocks = _fetch_all("CS", DATA / "_stocks.json", refresh)

    fund_tickers = {e["ticker"] for e in candidates}
    valid = fund_tickers | {s["ticker"] for s in stocks}

    records = []
    for e in candidates:
        rec = recognizer.build_record(e["ticker"], e.get("name", ""), valid, fund_tickers)
        if rec:
            records.append(rec)

    from collections import Counter
    by_conf = Counter(r["confidence"] for r in records)
    by_tier = Counter(r["tier"] for r in records)
    universe = {
        "generated": date.today().isoformat(),
        "count": len(records),
        "by_confidence": dict(by_conf),
        "by_tier": dict(by_tier),
        "records": sorted(records, key=lambda r: r["ticker"]),
    }
    (DATA / "letf_universe.json").write_text(json.dumps(universe, indent=2))
    return universe


def main() -> int:
    refresh = "--refresh" in sys.argv
    u = discover(refresh)
    print(f"\nfound {u['count']} leveraged/inverse ETFs")
    print(f"  by confidence: {u['by_confidence']}")
    print(f"  by tier:       {u['by_tier']}")
    print(f"wrote {DATA / 'letf_universe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
