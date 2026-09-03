"""
Simulates a two-turn conversation to test the confirm/deny flow:
  1. Customer sends a medium-confidence message -> bot asks to confirm
  2. Customer replies "yes" or "no" -> bot processes accordingly

Run: python test_confirmation_flow.py
"""

import json
from pathlib import Path
from app.classifier import classify, classify_confirmation
from app.router import decide, build_reply
from app.state import get_pending, set_pending, clear_pending

CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"
with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    catalog = json.load(f)

TEST_SENDER = "2348099999999_test"
clear_pending(TEST_SENDER)  # start clean


def turn_one(message: str):
    result = classify(message, catalog)
    decision = decide(result)
    print(f"\n📩 Turn 1: \"{message}\"")
    print(f"   intent={result.intent} confidence={result.confidence:.2f} action={decision.action}")

    if decision.action == "confirm_reply":
        reply = build_reply(result, catalog)
        set_pending(TEST_SENDER, result.intent, result.entities, reply)
        print(f"   bot: {reply}\n   (Did I get that right? Reply 'yes' to confirm or 'no' to talk to someone.)")
    else:
        print(f"   (not a confirm_reply case - test scenario expects medium confidence)")


def turn_two(message: str):
    pending = get_pending(TEST_SENDER)
    print(f"\n📩 Turn 2: \"{message}\"")
    if pending is None:
        print("   (no pending confirmation found - turn_one must set one first)")
        return

    confirmation = classify_confirmation(message)
    if confirmation == "yes":
        clear_pending(TEST_SENDER)
        print(f"   ✅ Confirmed - proceeding with intent '{pending['intent']}'")
    elif confirmation == "no":
        clear_pending(TEST_SENDER)
        print(f"   ❌ Rejected - escalating to human")
    else:
        print(f"   ⚠️ Not recognized as yes/no - would fall through as a new message")


# Scenario A: customer confirms
turn_one("I want to order 2 plates of amala")
turn_two("yes")

# Scenario B: customer rejects
turn_one("Do you have chicken suya")
turn_two("no, I meant something else")

# Scenario C: customer gives a clear "no"
turn_one("How much is delivery to Yaba")
turn_two("nope")
