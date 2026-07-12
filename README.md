# letf-finder

Find the leveraged / inverse ETFs related to any equity — self-updating, no
hand-maintained list. Point it at a ticker (NVDA, QQQ, TSLA) and get the 2x /
3x / inverse funds tied to it, each with a plain-English risk caveat.

**Decision-support, not advice.** Leveraged/inverse ETFs reset daily and decay
over time; every result says so.

## How it works

We **hardcode the recognizer, not the data.** Leveraged funds announce
themselves in their names ("Direxion Daily NVDA Bull 2X Shares"), so:

1. `discover.py` pulls every active ETF from Polygon's reference endpoint.
2. `recognizer.py` (pure, offline-tested) parses each name into
   `{factor, direction, underlying, tier, confidence}`.
3. Underlyings are validated against the live stock/ETF universe; low-confidence
   parses are flagged, not silently trusted.
4. `lookup.py` answers "what's related to X?" from the resulting
   `letf_universe.json`.

Re-run daily and new launches appear, closures drop off — zero manual edits.

## Status

See `roadmap.yaml` (render with `python roadmap.py --open`). Phase 1 is the data
foundation; sector relatedness (NVDA -> SOXL), metrics, and a UI are later
phases.

## Setup

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env    # add POLYGON_API_KEY
.venv/bin/python -m pytest tests/ -q            # recognizer + lookup, no network
.venv/bin/python -m letf.discover               # build the universe (needs key)
.venv/bin/python -m letf.lookup NVDA            # query it
```
