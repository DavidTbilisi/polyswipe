# Polyswipe

Turns your encoding-review system into an in-Anki loop, for **any language deck**.

- **scopes** — the languages you review. One entry per language:
  `{"name": "French", "deck": "French", "flag": "🇫🇷"}` — `deck` is the Anki deck-search
  substring (matches that deck and its subdecks); `name`/`flag` are just labels. Add more
  entries (German, Spanish…) and Polyswipe asks which one when you open Swipe or Stats.
- **auto_flag** — on answer, flag the card by how long you took (the tier ladder below).
- **respect_manual_flag** — if you pressed `Ctrl+N` yourself, keep your choice; only auto-flag
  when the card has no flag.
- **show_timer** / **timer_corner** — live encode-timer overlay and where it sits
  (`top-left` · `top-right` · `bottom-left` · `bottom-right`).
- **budgets** — `[max_seconds, anki_flag, name, colour]`, easiest first. Encoded within
  `max_seconds` → that flag.
- **over_flag / over_color** — slower than the last budget → this flag (red = rework).
- **swipe_batch** — how many unflagged cards to load per swipe session (a "set"; default 100).
- **unlock_batch** — how many locked cards **🔓 Polyswipe: Unlock next set** (`Ctrl+Shift+U`)
  unsuspends at a time (default 100). Batch loop: unlock a set → swipe those 100 → unlock the next.
- **swipe_autoplay** — auto-play each card's `[sound:…]` audio as it appears in the swipe deck.
  There's always a 🔊 button on the card and an `R` key to replay.
- **improve_tag** — swipe **up** (or ★ / `↑`) tags the note with this (default `polyswipe::improve`)
  to queue it for re-encoding; undo removes the tag. Find them later with `tag:polyswipe::improve`.
- **day_goal** — target for the "today" number in Stats.

Menu (Tools): **🃏 Polyswipe: Swipe** (`Ctrl+Shift+S`) · **📊 Polyswipe: Stats** (`Ctrl+Shift+F`).
