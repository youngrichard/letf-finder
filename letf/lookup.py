"""lookup(ticker) — given an equity/ETF, return its related leveraged/inverse
funds, ranked by directness, each carrying the risk caveats.

Reads data/letf_universe.json (built by discover.py).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# NOTE: the web UI (build_ui.py) carries a deliberately shorter version of this
# in its footer. If the substance changes, update both surfaces.
DECAY_CAVEAT = (
    "Leveraged/inverse ETFs reset daily — they do NOT deliver their multiple "
    "over periods longer than one day. Compounding and volatility decay erode "
    "returns in choppy markets, especially for inverse funds. Trade as a "
    "short-horizon vehicle, not a buy-and-hold."
)


def _load() -> dict:
    path = DATA / "letf_universe.json"
    if not path.exists():
        raise FileNotFoundError("run discover.py first to build the universe")
    return json.loads(path.read_text())


def lookup(ticker: str, universe: dict | None = None) -> dict:
    """Return related LETFs for `ticker`, grouped by tier (directness).

    Tier order = how directly related the LETF is to what you searched:
      direct   — a single-stock LETF on exactly this ticker
      index    — a leveraged/inverse fund on this index/ETF ticker
    Sector/thematic relatedness (e.g. NVDA -> SOXL) is Phase 2 (needs holdings).
    """
    u = universe or _load()
    t = ticker.upper()
    direct, index = [], []
    for r in u["records"]:
        if r["underlying"] != t:
            continue
        entry = {
            "ticker": r["ticker"],
            "name": r["name"],
            "factor": r["factor"],
            "direction": r["direction"],
            "confidence": r["confidence"],
        }
        (direct if r["tier"] == "single_stock" else index).append(entry)

    key = lambda e: (e["direction"] != "long", -(e["factor"] or 0))
    return {
        "query": t,
        "direct": sorted(direct, key=key),
        "index": sorted(index, key=key),
        "caveat": DECAY_CAVEAT,
        "note": "Sector/thematic matches (e.g. a chip stock -> a semiconductor "
                "LETF) are not included yet — that needs holdings data (Phase 2).",
    }


def format_result(res: dict) -> str:
    lines = [f"Leveraged / inverse funds related to {res['query']}:"]
    for tier, label in (("direct", "Direct (single-stock)"), ("index", "Index / ETF")):
        if res[tier]:
            lines.append(f"\n  {label}:")
            for e in res[tier]:
                fac = f"{e['factor']:+g}x" if e["factor"] is not None else "?x"
                flag = "" if e["confidence"] == "high" else f"  [{e['confidence']} confidence]"
                lines.append(f"    {e['ticker']:6s} {fac:5s} {e['name']}{flag}")
    if not res["direct"] and not res["index"]:
        lines.append("  (none found directly on this ticker)")
    lines.append(f"\n  ⚠ {res['caveat']}")
    lines.append(f"  {res['note']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    print(format_result(lookup(q)))
