#!/usr/bin/env python3
"""Live Polyswipe encoding-review dashboard (any language).

Reads live state from AnkiConnect and serves an auto-refreshing web page next to
Anki so the tier ladder, unlock progress, and red-rework queue update as you review.

Run:   python3 polyswipe/dashboard.py [DeckName]   # default: French
Then open http://127.0.0.1:8790  (keep it beside the Anki window).

The tier ladder mirrors the escalation system: a bigger time budget = a "harder"
colour. Red = failed the budget, revisit next round.
"""
import html
import http.server
import socketserver
import sys

import anki

PORT = 8790
LANG = sys.argv[1] if len(sys.argv) > 1 else "French"  # deck-name substring
DECK = f"deck:{LANG} card:1"  # recognition template only
DAY_GOAL = 1000

# (flag number, label, budget, css colour) in escalation order. Red handled separately.
TIERS = [
    (3, "green",     "≤5s",  "#3fb950"),
    (2, "orange",    "≤10s", "#f0883e"),
    (5, "pink",      "≤15s", "#f778ba"),
    (7, "purple",    "≤30s", "#a371f7"),
    (4, "blue",      "≤1m",  "#539bf5"),
    (6, "turquoise", "≤2m",  "#39c5cf"),
]
RED = (1, "red", "fail", "#f85149")


def collect():
    """One pass of live counts + the red-rework word list."""
    total = anki.count(DECK)
    unlocked = anki.count(f"{DECK} -is:suspended")
    reviewed_today = anki.count(f"{DECK} rated:1")

    tiers = []
    triaged = 0
    for flag, label, budget, colour in TIERS:
        n = anki.count(f"{DECK} flag:{flag}")
        triaged += n
        tiers.append({"label": label, "budget": budget, "colour": colour, "n": n})

    red_ids = anki.find(f"{DECK} flag:{RED[0]}")
    red_n = len(red_ids)
    triaged += red_n
    red_words = []
    for c in anki.cards_info(red_ids):
        f = c["fields"]
        red_words.append({
            "word": f.get("Word", {}).get("value", "?"),
            "hint": f.get("Hint", {}).get("value", ""),
        })
    red_words.sort(key=lambda w: w["word"])

    return {
        "total": total,
        "unlocked": unlocked,
        "locked": total - unlocked,
        "reviewed_today": reviewed_today,
        "triaged": triaged,
        "untouched": total - triaged,
        "tiers": tiers,
        "red_n": red_n,
        "red_words": red_words,
    }


def bar(pct, colour):
    return (f'<div class="track"><div class="fill" style="width:{pct:.1f}%;'
            f'background:{colour}"></div></div>')


def render(d):
    total = d["total"] or 1
    unlock_pct = 100 * d["unlocked"] / total
    triage_pct = 100 * d["triaged"] / total
    day_pct = min(100, 100 * d["reviewed_today"] / DAY_GOAL)
    tier_max = max([t["n"] for t in d["tiers"]] + [d["red_n"], 1])

    tier_rows = ""
    for t in d["tiers"]:
        w = 100 * t["n"] / tier_max
        tier_rows += f"""
        <div class="tier">
          <div class="tlabel"><span class="dot" style="background:{t['colour']}"></span>
            {t['label']}<span class="budget">{t['budget']}</span></div>
          <div class="track"><div class="fill" style="width:{w:.1f}%;background:{t['colour']}"></div></div>
          <div class="tn">{t['n']}</div>
        </div>"""
    rw = 100 * d["red_n"] / tier_max
    tier_rows += f"""
        <div class="tier red">
          <div class="tlabel"><span class="dot" style="background:{RED[3]}"></span>
            red<span class="budget">rework</span></div>
          <div class="track"><div class="fill" style="width:{rw:.1f}%;background:{RED[3]}"></div></div>
          <div class="tn">{d['red_n']}</div>
        </div>"""

    red_list = "".join(
        f'<li><b>{html.escape(w["word"])}</b>'
        f'<span>{html.escape(w["hint"])}</span></li>'
        for w in d["red_words"]
    ) or '<li class="empty">No reds yet — nothing to rework ✨</li>'

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta http-equiv="refresh" content="8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Polyswipe — {LANG}</title>
<style>
 *{{box-sizing:border-box;margin:0;padding:0}}
 body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#0d1117;color:#e6edf3;
   padding:24px;max-width:820px;margin:0 auto}}
 h1{{font-size:20px;font-weight:700;letter-spacing:-.02em}}
 h1 .fr{{color:#539bf5}}
 .sub{{color:#8b949e;font-size:13px;margin-top:2px}}
 .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}}
 .card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:16px}}
 .big{{font-size:30px;font-weight:700;line-height:1}}
 .cap{{color:#8b949e;font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
 .track{{height:10px;background:#21262d;border-radius:6px;overflow:hidden;margin-top:8px}}
 .fill{{height:100%;border-radius:6px;transition:width .4s}}
 .pctline{{display:flex;justify-content:space-between;font-size:12px;color:#8b949e;margin-top:6px}}
 section{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px;margin-bottom:16px}}
 section h2{{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#8b949e;margin-bottom:14px}}
 .tier{{display:grid;grid-template-columns:150px 1fr 40px;align-items:center;gap:12px;margin:9px 0}}
 .tlabel{{display:flex;align-items:center;gap:8px;font-weight:600;text-transform:capitalize}}
 .dot{{width:11px;height:11px;border-radius:50%;flex:none}}
 .budget{{color:#8b949e;font-weight:400;font-size:12px;margin-left:auto}}
 .tn{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}}
 .tier.red{{margin-top:14px;padding-top:14px;border-top:1px dashed #30363d}}
 ul{{list-style:none;columns:2;column-gap:24px}}
 li{{display:flex;flex-direction:column;padding:6px 0;break-inside:avoid;border-bottom:1px solid #21262d}}
 li b{{color:#f85149}} li span{{color:#8b949e;font-size:12px}}
 li.empty{{color:#3fb950;columns:1}}
 .foot{{color:#484f58;font-size:11px;text-align:center;margin-top:8px}}
</style></head><body>
 <h1>🃏 <span class="fr">{LANG}</span> encoding review
   <span style="font-weight:400;color:#8b949e;font-size:14px">· recognition pass</span></h1>
 <div class="sub">1k words/day goal · auto-refreshes every 8s · live from AnkiConnect</div>

 <div class="grid">
  <div class="card"><div class="cap">Unlocked</div>
    <div class="big">{d['unlocked']}<span style="font-size:16px;color:#8b949e">/{d['total']}</span></div>
    {bar(unlock_pct,'#539bf5')}
    <div class="pctline"><span>{unlock_pct:.0f}% active</span><span>{d['locked']} locked</span></div></div>
  <div class="card"><div class="cap">Triaged</div>
    <div class="big">{d['triaged']}<span style="font-size:16px;color:#8b949e">/{d['total']}</span></div>
    {bar(triage_pct,'#3fb950')}
    <div class="pctline"><span>{triage_pct:.0f}% flagged</span><span>{d['untouched']} to go</span></div></div>
  <div class="card"><div class="cap">Reviewed today</div>
    <div class="big">{d['reviewed_today']}</div>
    {bar(day_pct,'#a371f7')}
    <div class="pctline"><span>toward {DAY_GOAL}/day</span><span>{day_pct:.0f}%</span></div></div>
 </div>

 <section><h2>Tier ladder — how fast you encoded</h2>{tier_rows}</section>

 <section><h2>Red rework queue — {d['red_n']} words for the deep round</h2>
   <ul>{red_list}</ul></section>

 <div class="foot">tools/anki-french/dashboard.py</div>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        try:
            body = render(collect()).encode()
        except Exception as e:  # AnkiConnect down / Anki closed
            body = (f"<!doctype html><meta http-equiv=refresh content=4>"
                    f"<body style='font:16px sans-serif;background:#0d1117;color:#f85149;padding:40px'>"
                    f"<h2>Waiting for Anki…</h2><p>{html.escape(str(e))}</p>"
                    f"<p style='color:#8b949e'>Open Anki with the AnkiConnect add-on. Retrying…</p>"
                    f"</body>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Polyswipe {LANG} dashboard → http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
        httpd.serve_forever()
