"""Polyswipe — encode-timer HUD, auto-tier flagging, live stats, and a Tinder-style
swipe deck for any vocabulary deck (French, German, … — configurable per language).

Reviewer hooks show a live encode timer and flag each card by how long it took
(≤5s green … >2m red). The swipe deck triages unflagged cards fast: right = green,
left = red. Only card flags are ever written, and only in configured decks.
"""
import os
import re
import time
import json

from aqt import mw, gui_hooks
from aqt.qt import (QAction, QDialog, QVBoxLayout, QKeySequence, QTimer, Qt,
                    QInputDialog)
from aqt.utils import qconnect, tooltip
from aqt.webview import AnkiWebView

try:
    from aqt.sound import av_player
    from anki.sound import SoundOrVideoTag
    _HAVE_SOUND = True
except Exception:
    _HAVE_SOUND = False

ADDON_DIR = os.path.dirname(__file__)
PFX = "polyswipe:"


def _play(fn):
    if _HAVE_SOUND and fn:
        try:
            av_player.play_tags([SoundOrVideoTag(fn)])
        except Exception as e:
            print(PFX, "play:", e)


# ---------------------------------------------------------------- config
def cfg():
    c = mw.addonManager.getConfig(__name__) or {}
    c.setdefault("scopes", [{"name": "French", "deck": "French", "flag": "🇫🇷"}])
    c.setdefault("auto_flag", True)
    c.setdefault("show_timer", True)
    c.setdefault("timer_corner", "bottom-left")
    c.setdefault("respect_manual_flag", True)
    c.setdefault("day_goal", 1000)
    c.setdefault("budgets", [[5, 3, "green", "#3fb950"], [10, 2, "orange", "#f0883e"],
                             [15, 5, "pink", "#f778ba"], [30, 7, "purple", "#a371f7"],
                             [60, 4, "blue", "#539bf5"], [120, 6, "turquoise", "#39c5cf"]])
    c.setdefault("over_flag", 1)
    c.setdefault("over_color", "#f85149")
    c.setdefault("swipe_batch", 60)
    c.setdefault("swipe_autoplay", True)
    c.setdefault("improve_tag", "polyswipe::improve")
    return c


def _set_tag(cid, tag, add):
    try:
        note = mw.col.get_card(cid).note()
        (note.add_tag if add else note.remove_tag)(tag)
        mw.col.update_note(note)
    except Exception as e:
        print(PFX, "tag:", e)


def _scopes():
    return [s for s in (cfg().get("scopes") or []) if s.get("deck")]


def _pick_scope():
    """Return the chosen language scope, prompting only when more than one exists."""
    scopes = _scopes()
    if not scopes:
        tooltip("Polyswipe: no language decks configured (see add-on config)")
        return None
    if len(scopes) == 1:
        return scopes[0]
    labels = [f'{s.get("flag", "")} {s["name"]}'.strip() for s in scopes]
    item, ok = QInputDialog.getItem(mw, "Polyswipe", "Language:", labels, 0, False)
    return scopes[labels.index(item)] if ok else None


_STATE = {"shown_at": None, "cid": None}


def _in_scope(card):
    try:
        dn = mw.col.decks.name(card.did).lower()
        return any(s["deck"].lower() in dn for s in _scopes())
    except Exception:
        return False


def tier_for(elapsed, c):
    for secs, flag, _name, _col in sorted(c["budgets"]):
        if elapsed <= secs:
            return flag
    return c["over_flag"]


# ---------------------------------------------------------------- reviewer HUD
_TIMER_JS = r"""
(function(){
  var tiers = __TIERS__, over = __OVER__;
  var el = document.getElementById('ps-timer');
  if(!el){
    el = document.createElement('div'); el.id = 'ps-timer';
    el.style.cssText = 'position:fixed;__POS__;z-index:99999;'+
      'font:600 15px -apple-system,Segoe UI,sans-serif;padding:6px 12px;border-radius:10px;'+
      'background:rgba(13,17,23,.88);color:#e6edf3;border:2px solid #30363d;'+
      'box-shadow:0 2px 8px rgba(0,0,0,.4);min-width:120px;text-align:center';
    document.body.appendChild(el);
  }
  var start = Date.now();
  if(window.psInt) clearInterval(window.psInt);
  function paint(){
    var s = (Date.now()-start)/1000, col = over[0], name = over[1];
    for(var i=0;i<tiers.length;i++){ if(s<=tiers[i][0]){ col=tiers[i][1]; name=tiers[i][2]; break; } }
    el.style.borderColor = col; el.style.color = col;
    el.innerHTML = s.toFixed(1)+'s <span style="opacity:.7">→</span> '+name;
  }
  paint(); window.psInt = setInterval(paint, 100);
})();
"""


def on_show_question(card):
    try:
        _STATE["shown_at"] = time.monotonic()
        _STATE["cid"] = card.id
        c = cfg()
        if c["show_timer"] and _in_scope(card):
            tiers = [[b[0], b[3], b[2]] for b in sorted(c["budgets"])]
            pos = {"top-left": "top:10px;left:12px", "top-right": "top:10px;right:12px",
                   "bottom-left": "bottom:12px;left:12px",
                   "bottom-right": "bottom:12px;right:12px"}.get(
                       c["timer_corner"], "bottom:12px;left:12px")
            js = (_TIMER_JS.replace("__TIERS__", json.dumps(tiers))
                           .replace("__OVER__", json.dumps([c["over_color"], "red"]))
                           .replace("__POS__", pos))
            mw.reviewer.web.eval(js)
    except Exception as e:
        print(PFX, "show_question:", e)


def on_show_answer(card):
    try:
        mw.reviewer.web.eval("if(window.psInt){clearInterval(window.psInt);}")
    except Exception as e:
        print(PFX, "show_answer:", e)


def on_answer(reviewer, card, ease):
    try:
        c = cfg()
        if not (c["auto_flag"] and _in_scope(card)):
            return
        if _STATE["cid"] != card.id or _STATE["shown_at"] is None:
            return
        elapsed = time.monotonic() - _STATE["shown_at"]
        flag = tier_for(elapsed, c)
        cid = card.id

        def apply():
            try:
                if c["respect_manual_flag"] and mw.col.get_card(cid).user_flag() != 0:
                    return  # user chose their own flag — leave it
                mw.col.set_user_flag_for_cards(flag, [cid])
            except Exception as e:
                print(PFX, "apply:", e)

        QTimer.singleShot(20, apply)  # let Anki finish its own answer write first
    except Exception as e:
        print(PFX, "answer:", e)


# ---------------------------------------------------------------- stats window
def _metrics(scope):
    c = cfg()
    base = f'deck:{scope["deck"]} card:1'
    find = mw.col.find_cards
    total = len(find(base))
    unlocked = len(find(f"{base} -is:suspended"))
    today = len(find(f"{base} rated:1"))
    tiers, triaged = [], 0
    for secs, flag, name, col in sorted(c["budgets"]):
        n = len(find(f"{base} flag:{flag}"))
        triaged += n
        tiers.append((name, col, n))
    red_ids = find(f"{base} flag:{c['over_flag']}")
    triaged += len(red_ids)
    reds = []
    for cid in red_ids:
        try:
            reds.append(mw.col.get_card(cid).note().fields[0])
        except Exception:
            pass
    reds.sort()
    improves = []
    for cid in find(f"{base} tag:{c['improve_tag']}"):
        try:
            improves.append(mw.col.get_card(cid).note().fields[0])
        except Exception:
            pass
    improves.sort()
    return dict(total=total, unlocked=unlocked, today=today, triaged=triaged,
                tiers=tiers, reds=reds, improves=improves, over_col=c["over_color"],
                goal=c["day_goal"], name=scope["name"], flag=scope.get("flag", ""))


def _stats_html(scope):
    d = _metrics(scope)
    tmax = max([n for _, _, n in d["tiers"]] + [len(d["reds"]), 1])
    rows = ""
    for name, col, n in d["tiers"]:
        rows += (f'<div class=t><span class=dot style="background:{col}"></span>{name}'
                 f'<div class=tr><i style="width:{100*n/tmax:.0f}%;background:{col}"></i></div>'
                 f'<b>{n}</b></div>')
    rn = len(d["reds"])
    rows += (f'<div class="t red"><span class=dot style="background:{d["over_col"]}"></span>red'
             f'<div class=tr><i style="width:{100*rn/tmax:.0f}%;background:{d["over_col"]}"></i></div>'
             f'<b>{rn}</b></div>')
    reds = "".join(f"<li>{w}</li>" for w in d["reds"]) or "<li class=e>none — nothing to rework ✨</li>"
    ni = len(d["improves"])
    imps = "".join(f"<li>{w}</li>" for w in d["improves"]) or "<li class=e>none queued ✨</li>"
    return f"""<style>
 body{{font:14px -apple-system,Segoe UI,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:18px}}
 h1{{font-size:17px;margin:0 0 12px}} .fr{{color:#539bf5}}
 .g{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}}
 .c{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px}}
 .cap{{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
 .big{{font-size:24px;font-weight:700}} .big s{{font-size:13px;color:#8b949e;text-decoration:none}}
 .big.imp{{color:#539bf5}} ul.imp li{{color:#539bf5}}
 .t{{display:grid;grid-template-columns:90px 1fr 32px;align-items:center;gap:10px;margin:7px 0;text-transform:capitalize}}
 .dot{{width:10px;height:10px;border-radius:50%}}
 .tr{{height:9px;background:#21262d;border-radius:5px;overflow:hidden}} .tr i{{display:block;height:100%}}
 .t b{{text-align:right;font-variant-numeric:tabular-nums}}
 .t.red{{border-top:1px dashed #30363d;padding-top:10px;margin-top:12px}}
 h2{{font-size:12px;text-transform:uppercase;color:#8b949e;margin:16px 0 8px}}
 ul{{list-style:none;columns:3;padding:0;margin:0}} li{{color:#f85149;padding:3px 0;font-size:13px}}
 li.e{{color:#3fb950;columns:1}}
</style>
 <h1>{d['flag']} <span class=fr>{d['name']}</span> review</h1>
 <div class=g>
  <div class=c><div class=cap>Unlocked</div><div class=big>{d['unlocked']}<s>/{d['total']}</s></div></div>
  <div class=c><div class=cap>Triaged</div><div class=big>{d['triaged']}<s>/{d['total']}</s></div></div>
  <div class=c><div class=cap>Today</div><div class=big>{d['today']}<s>/{d['goal']}</s></div></div>
  <div class=c><div class=cap>Improve ★</div><div class="big imp">{ni}</div></div>
 </div>
 {rows}
 <h2>Red rework queue — {rn}</h2><ul>{reds}</ul>
 <h2>Improve queue ★ — {ni}</h2><ul class=imp>{imps}</ul>"""


class StatsDialog(QDialog):
    def __init__(self, scope):
        super().__init__(mw)
        self.scope = scope
        self.setWindowTitle(f"Polyswipe — {scope['name']} stats")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        self.resize(560, 620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.web = AnkiWebView(self)
        lay.addWidget(self.web)
        self.timer = QTimer(self)
        self.timer.setInterval(3000)
        qconnect(self.timer.timeout, self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self):
        try:
            self.web.stdHtml(_stats_html(self.scope))
        except Exception as e:
            self.web.stdHtml(f"<body style='color:#f85149;font-family:sans-serif;padding:20px'>{e}</body>")


_dialog = None


def show_stats():
    scope = _pick_scope()
    if not scope:
        return
    global _dialog
    _dialog = StatsDialog(scope)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


# ---------------------------------------------------------------- swipe deck
def _swipe_cards(scope):
    """Unlocked, untriaged (unflagged) recognition cards for this language, oldest first."""
    c = cfg()
    cids = mw.col.find_cards(f'deck:{scope["deck"]} card:1 -is:suspended')
    out = []
    for cid in cids:
        try:
            card = mw.col.get_card(cid)
            if card.user_flag() != 0:      # already triaged — skip
                continue
            n = card.note()
            g = lambda k: (n[k] if k in n else "")
            m = re.search(r"\[sound:(.*?)\]", g("Audio"))
            out.append({"id": cid, "word": g("Word"), "hint": g("Hint"),
                        "en": g("MnemonicEN"), "ru": g("MnemonicRU"),
                        "ka": g("MnemonicKA"), "theme": g("Theme"),
                        "audio": m.group(1) if m else ""})
            if len(out) >= c["swipe_batch"]:
                break
        except Exception as e:
            print(PFX, "swipe card:", e)
    return out


def _swipe_html(cards, scope):
    raw = open(os.path.join(ADDON_DIR, "swipe.html"), encoding="utf-8").read()
    style = raw[raw.find("<style>") + 7: raw.find("</style>")]
    body = raw[raw.find("<body>") + 6: raw.find("</body>")]
    data = ("<script>window.FR_CARDS=" + json.dumps(cards, ensure_ascii=False) + ";"
            "window.PS_FLAG=" + json.dumps(scope.get("flag", "")) + ";"
            "window.PS_LANG=" + json.dumps(scope["name"]) + ";"
            "window.PS_AUTOPLAY=" + json.dumps(bool(cfg()["swipe_autoplay"])) + ";</script>")
    return f"<style>{style}</style>{data}{body}"


class SwipeDialog(QDialog):
    def __init__(self, scope):
        super().__init__(mw)
        self.setWindowTitle(f"Polyswipe — {scope['name']}")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        self.resize(520, 830)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.web = AnkiWebView(self)
        lay.addWidget(self.web)
        cards = _swipe_cards(scope)
        self._n = len(cards)
        self.web.set_bridge_command(self._on_cmd, self)
        self.web.stdHtml(_swipe_html(cards, scope))

    def _on_cmd(self, cmd):
        try:
            if cmd.startswith("frplay:"):
                _play(cmd.split(":", 1)[1])
                return
            if not cmd.startswith("frdecide:"):
                return
            _, cid, decision = cmd.split(":", 2)
            cid = int(cid)
            c = cfg()
            if decision == "improve":
                _set_tag(cid, c["improve_tag"], True)
            elif decision == "unimprove":
                _set_tag(cid, c["improve_tag"], False)
            else:
                flag = {"green": c["budgets"][0][1], "red": c["over_flag"], "undo": 0}.get(decision)
                if flag is not None:
                    mw.col.set_user_flag_for_cards(flag, [cid])
        except Exception as e:
            print(PFX, "swipe cmd:", e)


_swipe = None


def show_swipe():
    scope = _pick_scope()
    if not scope:
        return
    global _swipe
    _swipe = SwipeDialog(scope)  # fresh queue each open
    if _swipe._n == 0:
        tooltip(f"No untriaged {scope['name']} cards to swipe — all flagged 🎉")
        return
    _swipe.show()
    _swipe.raise_()
    _swipe.activateWindow()


# ---------------------------------------------------------------- menu / wire up
def _install_menu():
    try:
        a1 = QAction("🃏 Polyswipe: Swipe", mw)
        a1.setShortcut(QKeySequence("Ctrl+Shift+S"))
        qconnect(a1.triggered, show_swipe)
        mw.form.menuTools.addAction(a1)
        a2 = QAction("📊 Polyswipe: Stats", mw)
        a2.setShortcut(QKeySequence("Ctrl+Shift+F"))
        qconnect(a2.triggered, show_stats)
        mw.form.menuTools.addAction(a2)
    except Exception as e:
        print(PFX, "menu:", e)


gui_hooks.reviewer_did_show_question.append(on_show_question)
gui_hooks.reviewer_did_show_answer.append(on_show_answer)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.main_window_did_init.append(_install_menu)
