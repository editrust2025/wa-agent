"""
WhatsApp AI Customer-Service Agent - MVP backend

Flow:
  360dialog webhook -> parse message -> classify intent -> route
  (auto-reply / confirm-reply / escalate to human) -> send WhatsApp reply -> log

Run locally:
  uvicorn app.main:app --reload --port 8000

Then point your 360dialog sandbox webhook URL at:
  https://<your-tunnel-or-deployment>/webhook
(use ngrok or a free Railway/Render deploy for a public URL during dev)
"""

import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response

from app.classifier import classify, classify_confirmation
from app.router import decide, build_reply
from app.logger import log_message
from app.whatsapp import send_text_message, alert_human_team
from app.state import get_pending, set_pending, clear_pending

load_dotenv()

app = FastAPI(title="WhatsApp AI Agent - MVP")

CATALOG_PATH = Path(__file__).parent.parent / "data" / "catalog.json"
BUSINESS_VERTICAL = os.getenv("BUSINESS_VERTICAL", "restaurant")
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")


def load_catalog() -> dict:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Meta's webhook verification handshake. When you set your webhook URL
    in the Meta App Dashboard, Meta sends this GET request to confirm you
    control the endpoint before it starts forwarding real messages."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    payload = await request.json()

    # Meta Cloud API webhook payloads nest the actual message inside
    # entry[].changes[].value.messages[]. Log the raw payload once during
    # setup if you want to see the exact shape before trusting this parsing.
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        messages = change.get("messages", [])
        if not messages:
            # Could be a status update (delivered/read) - ignore those
            return {"status": "ignored_non_message_event"}
        message = messages[0]
        sender = message["from"]  # customer's WhatsApp number
        text = message.get("text", {}).get("body", "")
    except (KeyError, IndexError):
        return {"status": "ignored_unparseable_payload"}

    if not text:
        return {"status": "ignored_non_text_message"}

    catalog = load_catalog()
    message_id = str(uuid.uuid4())

    # --- Check if we're waiting on a yes/no confirmation from this customer ---
    pending = get_pending(sender)
    if pending is not None:
        confirmation = classify_confirmation(text)
        if confirmation == "yes":
            clear_pending(sender)
            reply_text = "Great, confirmed! We'll proceed with that right away. ✅"
            log_message(
                message_id=message_id, raw_message=text, detected_language="unknown",
                intent_label=f"{pending['intent']}_confirmed", entities=pending["entities"],
                confidence=1.0, outcome="confirmed_by_customer", vertical=BUSINESS_VERTICAL,
            )
            await send_text_message(sender, reply_text)
            return {"status": "confirmed", "intent": pending["intent"]}

        if confirmation == "no":
            clear_pending(sender)
            await alert_human_team(sender, text, reason="customer rejected bot's understanding")
            reply_text = "Sorry about that! I'm connecting you with a team member to sort this out."
            log_message(
                message_id=message_id, raw_message=text, detected_language="unknown",
                intent_label=f"{pending['intent']}_rejected", entities=pending["entities"],
                confidence=1.0, outcome="escalated_to_human", vertical=BUSINESS_VERTICAL,
            )
            await send_text_message(sender, reply_text)
            return {"status": "rejected_escalated", "intent": pending["intent"]}

        # Message wasn't a clear yes/no - fall through and treat it as a new
        # message, but clear the stale pending state so it doesn't linger forever
        clear_pending(sender)

    # --- Normal classification path ---
    result = classify(text, catalog)
    decision = decide(result)
    outcome = "auto_resolved"

    if decision.action == "escalate":
        outcome = "escalated_to_human"
        await alert_human_team(sender, text, decision.reason)
        reply_text = (
            "Thanks for reaching out! I'm connecting you with a member of our "
            "team who'll get back to you shortly."
        )
    elif decision.action == "confirm_reply":
        outcome = "pending_confirmation"
        base_reply = build_reply(result, catalog)
        reply_text = f"{base_reply}\n\n(Did I get that right? Reply 'yes' to confirm or 'no' to talk to someone.)"
        set_pending(sender, result.intent, result.entities, reply_text)
    else:
        reply_text = build_reply(result, catalog)

    log_message(
        message_id=message_id,
        raw_message=text,
        detected_language=result.language_guess,
        intent_label=result.intent,
        entities=result.entities,
        confidence=result.confidence,
        outcome=outcome,
        vertical=BUSINESS_VERTICAL,
    )

    await send_text_message(sender, reply_text)

    return {"status": "handled", "intent": result.intent, "action": decision.action}
