# Polyswipe tools

Helpers for the vocabulary encoding-review system — make the review **observable**
(live dashboard) and **fast** (push encoding fixes straight into cards, no hand-pasting).
Works for any language deck. The primary UI is the **Polyswipe Anki add-on** (source in
[`addon/`](addon/)); these scripts are the AnkiConnect-side companions.

**Requires:** Anki open with the AnkiConnect add-on (id `2055492159`). Everything talks to
`http://127.0.0.1:8765`. Stdlib only, no pip installs.

## Install the add-on
The add-on source is vendored in [`addon/`](addon/). Symlink (or copy) it into Anki's
add-ons folder, then restart Anki:
```bash
ln -s "$PWD/addon" ~/.local/share/Anki2/addons21/polyswipe    # symlink: edits track the repo
# or: cp -r addon ~/.local/share/Anki2/addons21/polyswipe
```
Tools menu: **🃏 Polyswipe: Swipe** (`Ctrl+Shift+S`) · **📊 Polyswipe: Stats** (`Ctrl+Shift+F`).
Configure languages/timing in **Tools → Add-ons → Polyswipe → Config** (see `addon/config.md`).

## `dashboard.py` — live progress HUD (web)
```bash
python3 polyswipe/dashboard.py [DeckName]     # default: French → http://127.0.0.1:8790
```
Auto-refreshing web page: unlock progress, the tier ladder (green→turquoise by time budget),
today's pace toward the goal, and the **red rework queue**. Read-only. (The add-on's
**📊 Polyswipe: Stats** window is the same thing inside Anki.)

## `apply.py` — sync-safe writeback
```bash
python3 polyswipe/apply.py fixes.json                 # dry-run: before/after diff
python3 polyswipe/apply.py fixes.json --write         # apply
python3 polyswipe/apply.py fixes.json --deck=German   # another deck (default: French)
```
`fixes.json` maps a word to the fields to overwrite (any subset of
`MnemonicEN` / `MnemonicRU` / `MnemonicKA` / `SpellTrap` …). Dry-run is the default. Writes go
through Anki's own API (`updateNoteFields`) — sync-safe, no raw `collection.anki2` edits.

## `swipe.html` — Tinder-style triage UI
Self-contained swipe deck (drag / `←` `→` / buttons, `Space` to flip and reveal the
encoding). Swipe **right = green** (got it), **left = red** (rework). Works standalone in a
browser with mock cards for development; the **add-on** embeds this same file, feeds it real
cards, shows the picked language in the header, and writes flags on each swipe via
`mw.col.set_user_flag_for_cards`. In Anki: **Tools → 🃏 Polyswipe: Swipe** (`Ctrl+Shift+S`).

## The loop
1. Review in Anki — the add-on's timer auto-tiers by encode speed, or swipe to triage fast.
2. Watch progress in **📊 Polyswipe: Stats** (or `dashboard.py`).
3. For a weak encoding, name the word → Claude writes it into `fixes.json`.
4. `apply.py` dry-run to check the diff → `--write` to push it.

`anki.py` is the shared AnkiConnect client.
