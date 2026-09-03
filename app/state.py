"""
Minimal conversation state store, keyed by customer WhatsApp number.

Used to remember "I just sent a confirm_reply and I'm waiting for yes/no"
across separate webhook calls (each incoming message is a fresh HTTP request,
so without this the app has no memory of the previous turn).

This is a JSON file for MVP simplicity. Once you have real concurrent traffic
across multiple clients, swap this for SQLite or Redis - the three functions
below (get_pending, set_pending, clear_pending) are the whole interface,
so nothing else needs to change.
"""

import json
from pathlib import Path
from typing import Optional

STATE_PATH = Path(__file__).parent.parent / "data" / "conversation_state.json"


def _load() -> dict:
    if not STATE_PATH.exists():
        return {}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(state: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def get_pending(sender: str) -> Optional[dict]:
    """Returns the pending confirmation dict for this sender, or None."""
    state = _load()
    return state.get(sender)


def set_pending(sender: str, intent: str, entities: dict, reply_text: str):
    state = _load()
    state[sender] = {
        "intent": intent,
        "entities": entities,
        "reply_text": reply_text,
    }
    _save(state)


def clear_pending(sender: str):
    state = _load()
    if sender in state:
        del state[sender]
        _save(state)
