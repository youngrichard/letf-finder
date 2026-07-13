"""Build a self-contained search UI (docs/index.html, served by GitHub Pages)
from letf_universe.json.

One question -> one answer: search a stock/index/theme, get the leveraged &
inverse funds for it, grouped bullish/bearish, sorted by magnitude. No server;
data is inlined, search runs client-side. Open the file, or ?q=NVDA to prefill.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def main():
    universe = json.loads((DATA / "letf_universe.json").read_text())
    # factor=None records can't be placed in the long/short groups — exclude
    # them from the UI payload rather than letting them vanish silently in JS.
    recs = [{"t": r["ticker"], "n": r["name"], "f": r["factor"],
             "u": r["underlying"]}
            for r in universe["records"] if r["factor"] is not None]
    out_dir = ROOT / "docs"  # served by GitHub Pages
    out_dir.mkdir(exist_ok=True)
    html = (TEMPLATE.replace("__DATA__", json.dumps(recs))
            .replace("__COUNT__", str(universe["count"]))
            .replace("__GENERATED__", universe["generated"]))
    (out_dir / "index.html").write_text(html)
    print(f"wrote {out_dir / 'index.html'} ({len(recs)} funds)")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Leveraged &amp; Inverse ETFs</title>
<style>
:root{
--bg:#0c0d10;--surface:#16181d;--hover:#1c1f26;--text:#e9eaec;--muted:#8a8f98;
--faint:#565b63;--divider:#22252b;
--long:#00d16c;--long-bg:rgba(0,209,108,.14);
--short:#ff8a3d;--short-bg:rgba(255,138,61,.14);
}
*{box-sizing:border-box}
html,body{background:var(--bg)}
body{font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
color:var(--text);margin:0;padding:2.5rem 1.25rem 4rem;display:flex;justify-content:center;-webkit-font-smoothing:antialiased}
.wrap{width:100%;max-width:640px}
h1{font-size:24px;font-weight:600;letter-spacing:-.02em;margin:0 0 8px}
.tag{color:var(--muted);font-size:15px;line-height:1.5;margin:0 0 22px}
.search{position:relative}
#q{width:100%;padding:16px 18px;font-size:17px;font-weight:500;border:1px solid var(--divider);
border-radius:14px;background:var(--surface);color:var(--text);letter-spacing:-.01em}
#q::placeholder{color:var(--faint);font-weight:400}
#q:focus{outline:none;border-color:var(--long);box-shadow:0 0 0 3px var(--long-bg)}
.sec{font-size:13px;font-weight:600;letter-spacing:.02em;text-transform:uppercase;
color:var(--muted);margin:26px 0 6px}
.sec .n{color:var(--faint);font-weight:500;text-transform:none;letter-spacing:0}
.row{display:grid;grid-template-columns:58px 64px 1fr;align-items:center;gap:14px;
padding:13px 10px;border-radius:10px;transition:.1s}
.row:hover{background:var(--hover)}
.badge{font-size:13px;font-weight:600;text-align:center;padding:4px 0;border-radius:7px;letter-spacing:-.01em}
.b-long{background:var(--long-bg);color:var(--long)}
.b-short{background:var(--short-bg);color:var(--short)}
.tk{font-weight:600;letter-spacing:-.01em}
.nm{font-size:13.5px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.flag{font-size:11px;color:var(--faint)}
.empty{color:var(--faint);font-size:15px;margin-top:26px;line-height:1.6}
.foot{color:var(--faint);font-size:12px;margin-top:34px;border-top:1px solid var(--divider);padding-top:16px}
</style></head><body><div class="wrap">
<h1>Leveraged &amp; Inverse ETFs</h1>
<p class="tag">Search a ticker (NVDA), an index (QQQ), or a theme (semiconductor) to see the leveraged &amp; inverse funds for it.</p>
<div class="search"><input id="q" placeholder="Search a ticker or theme" autofocus autocomplete="off" spellcheck="false"></div>
<div id="out"></div>
<p class="foot">__COUNT__ funds &middot; generated __GENERATED__ &middot; these funds decay over time &middot; not advice</p>
</div>
<script>
const DATA=__DATA__;
const q=document.getElementById("q"),out=document.getElementById("out");
function esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML}
function fac(f){if(f==null)return "?";const s=f<0?"":"+";return s+(f%1?f:f.toFixed(0))+"\\u00D7"}
function card(r){
  const cls=r.f<0?"b-short":"b-long";
  return `<div class="row"><span class="badge ${cls}">${fac(r.f)}</span><span class="tk">${esc(r.t)}</span><span class="nm">${esc(r.n)}</span></div>`;
}
const CAP=60; // per group; substring searches can match hundreds of names
function run(){
  const s=q.value.trim().toLowerCase();
  if(!s){out.innerHTML="";return}
  const U=s.toUpperCase();
  // exact ticker/underlying at any length; substring matching needs >=3 chars
  // (1-2 chars would substring-match most of the universe)
  const hits=DATA.filter(r=>{
    if(r.u===U||r.t===U)return true;
    if(s.length<3)return false;
    return r.t.toLowerCase().includes(s)||r.n.toLowerCase().includes(s);
  });
  if(!hits.length){out.innerHTML=`<p class="empty">Nothing matches &ldquo;${esc(s)}&rdquo;. Sector matches by holdings are coming in a later version.</p>`;return}
  const bull=hits.filter(r=>r.f>0).sort((a,b)=>b.f-a.f);
  const bear=hits.filter(r=>r.f<0).sort((a,b)=>a.f-b.f);
  let h="";
  const grp=(list,label)=>{
    let g=`<div class="sec">${label}</div>`+list.slice(0,CAP).map(card).join("");
    if(list.length>CAP)g+=`<p class="empty">+ ${list.length-CAP} more &mdash; narrow the search</p>`;
    return g;
  };
  if(bull.length)h+=grp(bull,`Bullish <span class="n">long</span>`);
  if(bear.length)h+=grp(bear,`Bearish <span class="n">inverse</span>`);
  out.innerHTML=h;
}
q.addEventListener("input",run);
const pq=new URLSearchParams(location.search).get("q");
if(pq)q.value=pq;
run();
</script></body></html>"""


if __name__ == "__main__":
    main()
