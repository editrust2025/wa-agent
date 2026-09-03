"""
Bootstrap intent classifier.

This is a keyword/rule-based classifier meant to get you a working demo
BEFORE you have enough labeled pilot data to train a real ML model
(see intent_schema.json for the full intent list and training_data_seed.csv
for the seed dataset to eventually fine-tune on).

Swap this module out for a trained model (e.g. XLM-R / DistilBERT via
sentence-transformers or a fine-tuned classifier) once you have 150-300+
real labeled examples from your pilot. The interface (classify() returning
an IntentResult) should stay the same so nothing else in the app needs to change.
"""

from dataclasses import dataclass, field
from typing import Optional
import re

@dataclass
class IntentResult:
    intent: str
    confidence: float
    entities: dict = field(default_factory=dict)
    language_guess: str = "unknown"


# Keyword patterns per intent. Order matters: more specific/urgent intents
# (complaint, human handoff, dietary) are checked first so they never get
# masked by a generic price/availability match.
INTENT_PATTERNS = {
    "human_handoff_request": [
        r"\bspeak to (a )?(human|someone|person|manager|agent)\b",
        r"\btalk to (a )?(human|someone|person|manager)\b",
        r"\bconnect me to\b",
        r"\bfit help\b",
    ],
    "dietary_restriction_check": [
        r"\ballerg(y|ic|en)\b",
        r"\bcontain(s)? (peanut|nut|dairy|gluten|seafood)s?\b",
        r"\bvegan\b",
        r"\bvegetarian\b",
    ],
    "complaint": [
        r"\b(don craze|is broken|is damaged|defect(ive)?)\b",
        r"\b(never arrive|not arrived|no show)\b",
        r"\brefund\b",
        r"\bwrong order\b",
        r"\bcold and late\b",
        r"\bcomplain\b",
    ],
    "greeting": [
        r"^\s*(hi|hello|hey|good morning|good afternoon|good evening|e ?kaaro)\b",
    ],
    "farewell": [
        r"\b(thanks|thank you|bye|e se|god bless)\b",
    ],
    "menu_request": [
        r"\bmenu\b",
        r"\bwhat dishes\b",
        r"\bwhat (do|una) (you|dey) (have|get)\b",
    ],
    "table_reservation": [
        r"\bbook a table\b",
        r"\breserve a table\b",
        r"\bbook table\b",
    ],
    "size_guide_request": [
        r"\bsize guide\b",
        r"\bsize chart\b",
        r"\bwhat size\b",
    ],
    "return_exchange_policy": [
        r"\breturn policy\b",
        r"\bexchange\b.*\bfor\b",
        r"\bwan return\b",
    ],
    "delivery_inquiry": [
        r"\bdelivery\b",
        r"\bwhen will (it|my order) arrive\b",
        r"\bdeliver to\b",
    ],
    "payment_inquiry": [
        r"\bhow do i pay\b",
        r"\bhow (do|una) pay\b",
        r"\bdiscount\b",
        r"\bpromo\b",
        r"\baccept (transfer|card)\b",
    ],
    "availability_check": [
        r"\bdo you have\b",
        r"\bis this in stock\b",
        r"\bstill available\b",
        r"\buna get\b",
        r"\bstill get\b",
    ],
    "order_place": [
        r"\bi want to order\b",
        r"\bi'?d like to order\b",
        r"\bsend me\b",
        r"\bi wan buy\b",
        r"\bmake i get\b",
        r"\bplease send\b",
    ],
    "price_inquiry": [
        r"\bhow much\b",
        r"\bprice of\b",
        r"\bwetin be price\b",
        r"\belo ni\b",
    ],
    "follow_up": [
        r"\bany update\b",
        r"\bstill waiting\b",
        r"\bwetin dey happen\b",
    ],
}

PIDGIN_MARKERS = ["una", "wetin", "abeg", "dey", "don", "wan", "fit", "no be", "e go", "make i"]
YORUBA_MARKERS = ["elo", "ese", "kaaro", "aso"]

AFFIRMATIVE_PATTERNS = [
    # Matches the whole message being just an affirmation, e.g. "yes", "ok!"
    r"^\s*(yes|yeah|yep|yup|correct|that'?s right|ok|okay|sure|confirm(ed)?)\s*[.!,]?\s*$",
    r"^\s*(na so|e correct|no wahala|na him be that)\s*[.!,]?\s*$",
    # Matches an affirmation as the leading word even if more text follows,
    # e.g. "yes please", "yeah that's it"
    r"^\s*(yes|yeah|yep|yup|correct|okay|sure)\b[\s,]",
]
NEGATIVE_PATTERNS = [
    r"^\s*(no|nope|nah|wrong|not (correct|right)|incorrect)\s*[.!,]?\s*$",
    r"^\s*(no be so|e no correct)\s*[.!,]?\s*$",
    # Matches a negation as the leading word even if more text follows,
    # e.g. "no, I meant something else"
    r"^\s*(no|nope|nah)\b[\s,]",
]


def classify_confirmation(text: str) -> Optional[str]:
    """Returns 'yes', 'no', or None if the message isn't a clear yes/no reply.
    Used only when the app is expecting a confirmation from a previous
    confirm_reply turn - see app/state.py."""
    lower = text.lower().strip()
    for pattern in AFFIRMATIVE_PATTERNS:
        if re.search(pattern, lower):
            return "yes"
    for pattern in NEGATIVE_PATTERNS:
        if re.search(pattern, lower):
            return "no"
    return None


def guess_language(text: str) -> str:
    lower = text.lower()
    if any(m in lower for m in YORUBA_MARKERS):
        return "yoruba"
    if any(m in lower for m in PIDGIN_MARKERS):
        return "pidgin"
    return "english"


def extract_entities(text: str, catalog: dict) -> dict:
    """Very lightweight entity extraction via catalog lookup + regex.
    Replace with spaCy NER + a proper gazetteer once you have real volume."""
    entities = {}
    lower = text.lower()

    # product_name via alias lookup
    for product in catalog.get("products", []):
        for alias in [product["name"].lower()] + [a.lower() for a in product.get("aliases", [])]:
            if alias in lower:
                entities["product_name"] = product["name"]
                break
        if "product_name" in entities:
            break

    # location via delivery zones
    for zone in catalog.get("delivery_zones", []):
        if zone["location"].lower() in lower:
            entities["location"] = zone["location"]
            break

    # quantity - simple digit or spelled-out number before "plate(s)"/"of"
    qty_match = re.search(r"\b(\d+)\b", text)
    if qty_match:
        entities["quantity"] = int(qty_match.group(1))

    # size - digits following "size"
    size_match = re.search(r"\bsize\s*(\d{1,2}|[smlxSMLX]{1,3})\b", lower)
    if size_match:
        entities["size"] = size_match.group(1).upper()

    return entities


def classify(text: str, catalog: Optional[dict] = None) -> IntentResult:
    catalog = catalog or {}
    lower = text.lower().strip()

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower):
                entities = extract_entities(text, catalog)
                # Keyword match on a high-signal pattern -> treat as high confidence.
                # This is intentionally simple; once you have a trained model,
                # replace this whole function body and keep the same return type.
                confidence = 0.90 if intent in (
                    "human_handoff_request", "dietary_restriction_check", "complaint"
                ) else 0.80
                return IntentResult(
                    intent=intent,
                    confidence=confidence,
                    entities=entities,
                    language_guess=guess_language(text),
                )

    # Nothing matched -> low confidence, route to LLM/human per routing rules
    return IntentResult(
        intent="unknown",
        confidence=0.20,
        entities=extract_entities(text, catalog),
        language_guess=guess_language(text),
    )
