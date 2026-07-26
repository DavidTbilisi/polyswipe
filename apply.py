#!/usr/bin/env python3
"""Push encoding fixes into vocab cards via AnkiConnect (sync-safe, no raw DB edits).

Input JSON maps a word to the fields to overwrite (any subset):

    {
      "acheter":  {"MnemonicEN": "...", "MnemonicRU": "...", "MnemonicKA": "..."},
      "le canard": {"SpellTrap": "..."}
    }

Usage:
    python3 polyswipe/apply.py fixes.json                 # dry-run: show before/after
    python3 polyswipe/apply.py fixes.json --write         # actually apply
    python3 polyswipe/apply.py fixes.json --deck=German   # target another deck (default: French)

Dry-run is the default so nothing changes until you've eyeballed the diff.
"""
import json
import sys

import anki

FIELDS = ("Word", "Hint", "MnemonicEN", "MnemonicRU", "MnemonicKA", "SpellTrap")


def _deck():
    for a in sys.argv:
        if a.startswith("--deck="):
            return a.split("=", 1)[1]
    if "--deck" in sys.argv:
        i = sys.argv.index("--deck")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return "French"


DECK = f"deck:{_deck()} card:1"


def build_word_map():
    """word (lowercased, stripped) -> (note_id, current_fields)."""
    nids = anki.invoke("findNotes", query=DECK)
    m = {}
    for n in anki.notes_info(nids):
        w = n["fields"].get("Word", {}).get("value", "").strip()
        m[w.lower()] = (n["noteId"], {k: v["value"] for k, v in n["fields"].items()})
    return m


def match(word, wmap):
    w = word.strip().lower()
    if w in wmap:
        return wmap[w]
    # forgiving: ignore leading article, then prefix match
    hits = [v for k, v in wmap.items() if k == w or k.startswith(w) or w in k]
    return hits[0] if len(hits) == 1 else None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    write = "--write" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)

    fixes = json.load(open(args[0]))
    wmap = build_word_map()

    applied, skipped = 0, 0
    for word, newfields in fixes.items():
        hit = match(word, wmap)
        if not hit:
            print(f"  ⚠️  no unique match for {word!r} — skipped")
            skipped += 1
            continue
        nid, cur = hit
        bad = [k for k in newfields if k not in FIELDS]
        if bad:
            print(f"  ⚠️  {word}: unknown field(s) {bad} — skipped")
            skipped += 1
            continue

        print(f"\n● {word}  (note {nid})")
        changed = {}
        for k, new in newfields.items():
            old = cur.get(k, "")
            if old.strip() == str(new).strip():
                continue
            changed[k] = new
            print(f"    {k}:")
            print(f"      – {old or '(empty)'}")
            print(f"      + {new}")
        if not changed:
            print("    (no change)")
            continue
        if write:
            anki.update_fields(nid, changed)
            print("    ✓ written")
        applied += 1

    mode = "APPLIED" if write else "DRY-RUN (nothing written — add --write)"
    print(f"\n{mode}: {applied} card(s) to change, {skipped} skipped")


if __name__ == "__main__":
    main()
