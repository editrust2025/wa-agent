"""
Quick sanity check - run the classifier + router on sample messages without
needing WhatsApp/360dialog connected yet.

Run: python test_locally.py
"""

import json
from pathlib import Path
from app.classifier import classify
from app.router import decide, build_reply

CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"

with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    catalog = json.load(f)

test_messages = [
    "Hi",
    "How much is jollof rice",
    "Do you have chicken suya",
    "I want to order 2 plates of fried rice",
    "How much is delivery to Lekki",
    "This food I ordered was cold and late",
    "Let me speak to someone",
    "Does the suya contain peanuts",
    "Send me una menu",
    "I wan buy 3 plates of amala",
    "Thanks",
]

for msg in test_messages:
    result = classify(msg, catalog)
    decision = decide(result)
    reply = build_reply(result, catalog) if decision.action != "escalate" else "[ESCALATED TO HUMAN]"

    print(f"\n📩 \"{msg}\"")
    print(f"   intent={result.intent} confidence={result.confidence:.2f} language={result.language_guess}")
    print(f"   entities={result.entities}")
    print(f"   action={decision.action} ({decision.reason})")
    print(f"   reply: {reply}")
