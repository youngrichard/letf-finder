"""ai-roadmap — render a repo-local roadmap.yaml into a self-contained HTML
dashboard you (and your AI agent) keep current.

The YAML is the single source of truth. This renderer is read-only: it never
edits the roadmap, only visualizes it. The agent updates the YAML as part of
doing the work (see skill/SKILL.md); you glance at the HTML to see status.

Usage:
    python roadmap.py                      # render ./roadmap.yaml -> ./roadmap.html
    python roadmap.py --input path.yaml --output out.html
    python roadmap.py --open               # render then open in browser
    python roadmap.py --check              # exit 1 if YAML is malformed (for CI)
"""

from __future__ import annotations

import argparse
import html
import sys
import webbrowser
from pathlib import Path

import yaml

STATUS = {
    "planned":     ("planned",     "#888780", "#F1EFE8"),
    "in_progress": ("in progress", "#185FA5", "#E6F1FB"),
    "done":        ("done",        "#3B6D11", "#EAF3DE"),
    "blocked":     ("blocked",     "#A32D2D", "#FCEBEB"),
}


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if data is None:
        raise ValueError("roadmap file is empty")
    if not isinstance(data, dict):
        raise ValueError("roadmap must be a mapping (key: value), not a list or scalar")
    if "phases" not in data:
        raise ValueError("roadmap needs a top-level 'phases:' list")
    if not isinstance(data["phases"], list):
        raise ValueError("'phases' must be a list")
    for i, ph in enumerate(data["phases"]):
        where = f"phase {i + 1}"
        if not isinstance(ph, dict):
            raise ValueError(f"{where}: each phase must be a mapping")
        if not ph.get("name"):
            raise ValueError(f"{where}: missing required 'name'")
        ph.setdefault("status", "planned")
        if ph["status"] not in STATUS:
            raise ValueError(
                f"{where} ({ph['name']}): bad status {ph['status']!r} — "
                f"use one of {', '.join(STATUS)}")
        crit = ph.setdefault("success_criteria", [])
        if not isinstance(crit, list):
            raise ValueError(f"{where}: 'success_criteria' must be a list")
        ph.setdefault("deferred", ph.get("out_of_scope", []))  # back-compat
        ph.setdefault("changelog", [])
    return data


def _progress(phase: dict) -> tuple[int, int]:
    crit = phase["success_criteria"]
    return sum(1 for c in crit if c.get("done")), len(crit)


def _dates(phase: dict) -> tuple[str, str]:
    """started = earliest changelog date, updated = latest. '' if none."""
    dates = sorted(str(e.get("date", "")) for e in phase.get("changelog", [])
                   if e.get("date"))
    return (dates[0], dates[-1]) if dates else ("", "")


def _mark(done: bool) -> str:
    cls = "m-done" if done else "m-todo"
    return f'<span class="mark {cls}">{"&#10003;" if done else ""}</span>'


def _phase_html(ph: dict) -> str:
    label, color, bg = STATUS[ph["status"]]
    done, total = _progress(ph)
    pct = round(done / total * 100) if total else (100 if ph["status"] == "done" else 0)
    featured = ph["status"] == "in_progress"
    started, updated = _dates(ph)

    meta = " &middot; ".join(
        x for x in (f"started {started}" if started else "",
                    f"updated {updated}" if updated else "") if x)

    crit_html = "".join(
        f'<div class="crit {"c-done" if c.get("done") else ""}">'
        f'{_mark(bool(c.get("done")))}'
        f'<span class="ct">{html.escape(str(c.get("text", c)))}</span></div>'
        for c in ph["success_criteria"]
    )

    deferred = ph.get("deferred", [])
    deferred_html = (
        '<div class="deferred"><span class="dh">deferred</span> '
        + "; ".join(html.escape(str(x)) for x in deferred) + "</div>"
    ) if deferred else ""

    goal = html.escape((ph.get("goal") or "").strip())
    return f"""
    <section class="phase{' featured' if featured else ''}">
      <div class="phdr">
        <span class="pname">Phase {ph.get('id','')} — {html.escape(ph['name'])}</span>
        <span class="chip" style="color:{color};background:{bg}">{label}</span>
      </div>
      {f'<div class="pmeta">{meta}</div>' if meta else ''}
      {f'<div class="goal">{goal}</div>' if goal else ''}
      <div class="bar"><div class="fill" style="--w:{pct}%;width:{pct}%;background:{color}"></div></div>
      <div class="prog">{done}/{total} criteria</div>
      {f'<div class="crits">{crit_html}</div>' if crit_html else ''}
      {deferred_html}
    </section>"""


def render(data: dict) -> str:
    phases = data["phases"]
    body = "".join(_phase_html(p) for p in phases)

    done_ph = sum(1 for p in phases if p["status"] == "done")
    crit_done = sum(_progress(p)[0] for p in phases)
    crit_total = sum(_progress(p)[1] for p in phases)
    overall = round(crit_done / crit_total * 100) if crit_total else 0

    proj = html.escape(str(data.get("project", "Roadmap")))
    desc = html.escape(str(data.get("description", "")))
    updated = html.escape(str(data.get("updated", "")))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{proj} — roadmap</title>
<style>
:root{{--bg:#faf9f5;--surface:#fff;--card:#f7f6f0;--text:#1a1a18;--muted:#6b6a63;--faint:#9b9a92;--border:#e4e2d8}}
@media(prefers-color-scheme:dark){{:root{{--bg:#1f1e1b;--surface:#2a2926;--card:#242320;--text:#ece9e0;--muted:#a3a199;--faint:#75746d;--border:#3a3833}}}}
*{{box-sizing:border-box}}
body{{font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);margin:0;padding:2rem 1rem;display:flex;justify-content:center}}
.wrap{{width:100%;max-width:720px}}
h1{{font-size:22px;font-weight:500;margin:0 0 4px}}
.sub{{color:var(--muted);font-size:14px;margin:0 0 12px}}
.obar{{height:8px;background:var(--card);border-radius:20px;overflow:hidden;margin:0 0 6px}}
.ofill{{height:100%;background:#185FA5;animation:grow .9s cubic-bezier(.4,0,.2,1) both}}
@keyframes grow{{from{{width:0}}to{{width:var(--w)}}}}
@media(prefers-reduced-motion:reduce){{.ofill,.fill{{animation:none}}}}
.ometa{{color:var(--faint);font-size:12px;margin:0 0 1.75rem}}
.phase{{background:var(--card);border-radius:12px;padding:1rem 1.25rem;margin:12px 0}}
.phase.featured{{background:var(--surface);border:2px solid #185FA5}}
.phdr{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.pname{{font-size:15px;font-weight:500}}
.chip{{font-size:12px;padding:2px 10px;border-radius:20px}}
.pmeta{{color:var(--faint);font-size:12px;margin:5px 0 0}}
.goal{{color:var(--muted);font-size:13px;margin:8px 0 0}}
.bar{{height:6px;background:var(--bg);border-radius:20px;overflow:hidden;margin:12px 0 4px}}
.fill{{height:100%;animation:grow .9s cubic-bezier(.4,0,.2,1) both}}
.prog{{color:var(--faint);font-size:11px;margin-bottom:10px}}
.crits{{border-top:.5px solid var(--border);padding-top:10px}}
.crit{{font-size:13px;color:var(--muted);line-height:1.5;display:flex;gap:8px;align-items:center;margin:6px 0}}
.crit.c-done{{color:var(--text)}}
.ct{{flex:1}}
.mark{{flex:none;width:16px;height:16px;border-radius:50%;font-size:11px;line-height:15px;text-align:center;border:1.5px solid var(--faint);color:#fff}}
.m-done{{background:#3B6D11;border-color:#3B6D11}}
.deferred{{font-size:12px;color:var(--faint);margin-top:12px;line-height:1.7}}
.dh{{text-transform:lowercase;color:var(--faint);font-weight:500;margin-right:4px}}
</style></head><body><div class="wrap">
<h1>{proj}</h1>
{f'<p class="sub">{desc}</p>' if desc else ''}
<div class="obar"><div class="ofill" style="--w:{overall}%;width:{overall}%"></div></div>
<p class="ometa">{overall}% of criteria complete &middot; {done_ph}/{len(phases)} phases done &middot; updated {updated}</p>
{body}
</div></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render roadmap.yaml to HTML.")
    ap.add_argument("--input", default="roadmap.yaml")
    ap.add_argument("--output", default="roadmap.html")
    ap.add_argument("--open", action="store_true", help="open in browser after render")
    ap.add_argument("--check", action="store_true", help="validate only, no render")
    args = ap.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"no {path} found", file=sys.stderr)
        return 1
    try:
        data = load(path)
    except (yaml.YAMLError, ValueError) as e:
        print(f"invalid roadmap: {e}", file=sys.stderr)
        return 1
    if args.check:
        print(f"ok: {len(data['phases'])} phases")
        return 0

    out = Path(args.output)
    out.write_text(render(data))
    print(f"wrote {out}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
