"""
Direct integration with Meta's WhatsApp Cloud API (no BSP in between).

Requires:
- A Meta Developer app with the WhatsApp product added
- A permanent access token from a System User (Business Settings -> System Users)
  (temporary tokens from the dashboard expire after 24h - don't use those in production)
- Your Phone Number ID (found under WhatsApp -> API Setup in the dashboard)

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api

Important 24-hour window rule: you can only send free-form text messages
(what send_text_message does below) within 24 hours of the customer's last
message. Outside that window, you must use a pre-approved message template.
For this MVP - where the bot only replies to inbound customer messages -
you'll always be inside that window, so this isn't a concern yet. It matters
later if you add proactive follow-ups (e.g. "still interested?" nudges to
leads who went quiet).
"""

import os
import httpx

WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN", "")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")
WA_GRAPH_VERSION = os.getenv("WA_GRAPH_VERSION", "v21.0")
WA_API_BASE_URL = f"https://graph.facebook.com/{WA_GRAPH_VERSION}/{WA_PHONE_NUMBER_ID}"

HUMAN_ESCALATION_NUMBERS = [
    n.strip() for n in os.getenv("HUMAN_ESCALATION_NUMBERS", "").split(",") if n.strip()
]


async def send_text_message(to: str, body: str) -> dict:
    """Send a plain text reply to a customer's WhatsApp number.
    `to` should be in international format without a leading '+' or '00',
    e.g. '2348012345678'."""
    url = f"{WA_API_BASE_URL}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            # Meta's error payloads are informative - surface them rather than
            # swallowing into a generic httpx exception.
            print(f"[error] WhatsApp send failed ({resp.status_code}): {resp.text}")
        resp.raise_for_status()
        return resp.json()


async def alert_human_team(customer_number: str, message: str, reason: str):
    """Notify your team (or yourself, during pilot) that a conversation needs
    a human. For MVP this just sends a WhatsApp message to your own number(s);
    swap for a Slack webhook or dashboard alert once you have a real team."""
    alert_text = (
        f"🔔 Escalation needed\n"
        f"From: {customer_number}\n"
        f"Reason: {reason}\n"
        f"Message: \"{message}\""
    )
    for number in HUMAN_ESCALATION_NUMBERS:
        try:
            await send_text_message(number, alert_text)
        except Exception as e:
            # Don't let an alert failure crash the webhook handler
            print(f"[warn] failed to alert {number}: {e}")
