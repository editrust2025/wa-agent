"""
Routing logic: decides what happens to a classified message.

Mirrors the confidence_routing_rules in intent_schema.json:
- high confidence, safe intent -> answer directly from templates/catalog
- medium confidence -> answer but ask the customer to confirm
- low confidence, or a sensitive intent -> escalate to a human
"""

from dataclasses import dataclass
from app.classifier import IntentResult

ALWAYS_ESCALATE = {"human_handoff_request", "dietary_restriction_check", "complaint"}

CONFIDENCE_HIGH = 0.85
CONFIDENCE_MEDIUM = 0.50


@dataclass
class RoutingDecision:
    action: str  # "auto_reply" | "confirm_reply" | "escalate"
    reason: str


def decide(result: IntentResult) -> RoutingDecision:
    if result.intent in ALWAYS_ESCALATE:
        return RoutingDecision(action="escalate", reason=f"intent '{result.intent}' always escalates")

    if result.confidence >= CONFIDENCE_HIGH:
        return RoutingDecision(action="auto_reply", reason="high confidence match")

    if result.confidence >= CONFIDENCE_MEDIUM:
        return RoutingDecision(action="confirm_reply", reason="medium confidence match")

    return RoutingDecision(action="escalate", reason="low confidence / unrecognized message")


def build_reply(result: IntentResult, catalog: dict) -> str:
    """Generate the actual reply text for auto/confirm-reply cases.
    This is deliberately template-based for the MVP - swap in DB lookups
    or an LLM call for richer replies as you scale."""

    intent = result.intent
    entities = result.entities

    if intent == "greeting":
        return "Hi there! 👋 How can I help you today? You can ask about our menu, prices, or place an order."

    if intent == "farewell":
        return "You're welcome! Have a great day 😊"

    if intent == "menu_request":
        items = catalog.get("products", [])
        lines = [f"- {p['name']}: ₦{p['price_naira']:,}" for p in items if p.get("available")]
        return "Here's our menu:\n" + "\n".join(lines)

    if intent == "price_inquiry":
        product_name = entities.get("product_name")
        if product_name:
            for p in catalog.get("products", []):
                if p["name"] == product_name:
                    return f"{p['name']} is ₦{p['price_naira']:,}."
        return "Which item would you like the price for? You can also type 'menu' to see everything."

    if intent == "availability_check":
        product_name = entities.get("product_name")
        if product_name:
            for p in catalog.get("products", []):
                if p["name"] == product_name:
                    status = "yes, it's available!" if p.get("available") else "sorry, that's out of stock right now."
                    return f"{p['name']} - {status}"
        return "Could you tell me the item name so I can check availability?"

    if intent == "delivery_inquiry":
        location = entities.get("location")
        if location:
            for z in catalog.get("delivery_zones", []):
                if z["location"] == location:
                    return f"Delivery to {z['location']} is ₦{z['fee_naira']:,}."
        zones = ", ".join(z["location"] for z in catalog.get("delivery_zones", []))
        return f"We currently deliver to: {zones}. Which area are you in?"

    if intent == "order_place":
        product_name = entities.get("product_name")
        quantity = entities.get("quantity", 1)
        if product_name:
            return (f"Got it - {quantity} x {product_name}. "
                    f"Please confirm and share your delivery address to proceed.")
        return "Sure! What would you like to order?"

    if intent == "payment_inquiry":
        return "We accept bank transfer and card payments. We'll send account details once your order is confirmed."

    if intent == "table_reservation":
        return "I'd love to help book that table! Could you confirm the date, time, and number of guests?"

    if intent == "size_guide_request":
        return "Here's a general guide: S (36-38), M (40-42), L (44-46), XL (48-50). Want me to check a specific item's fit?"

    if intent == "return_exchange_policy":
        return "Items can be returned or exchanged within 7 days if unused and in original condition. Do you have an order ID?"

    if intent == "follow_up":
        return "Thanks for following up! Let me check on that for you - one moment."

    return "Thanks for your message! Let me get someone to help with that."
