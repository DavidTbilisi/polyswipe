"""Tiny AnkiConnect client (stdlib only).

AnkiConnect must be running (add-on 2055492159) with Anki open.
Docs: https://foosoft.net/projects/anki-connect/
"""
import json
import urllib.request

ENDPOINT = "http://127.0.0.1:8765"


def invoke(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(ENDPOINT, data=payload)
    with urllib.request.urlopen(req, timeout=15) as resp:
        out = json.load(resp)
    if out.get("error"):
        raise RuntimeError(f"AnkiConnect {action}: {out['error']}")
    return out["result"]


def count(query):
    return len(invoke("findCards", query=query))


def find(query):
    return invoke("findCards", query=query)


def cards_info(card_ids):
    if not card_ids:
        return []
    return invoke("cardsInfo", cards=card_ids)


def notes_info(note_ids):
    if not note_ids:
        return []
    return invoke("notesInfo", notes=note_ids)


def update_fields(note_id, fields):
    """fields = {'MnemonicEN': '...', ...}. Sync-safe writeback via Anki's API."""
    return invoke("updateNoteFields", note={"id": note_id, "fields": fields})
