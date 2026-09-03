"""
Logs every incoming message + how it was handled, in the same schema as
production_logging_schema in intent_schema.json. During your pilot, export
this CSV regularly and manually correct the intent_label column - that
corrected file becomes your real training data for the ML model upgrade.
"""

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).parent.parent / "data" / "conversation_log.csv"

FIELDNAMES = [
    "message_id", "timestamp", "raw_message", "detected_language",
    "intent_label", "entities", "confidence", "outcome", "vertical", "client_id",
]


def _ensure_header():
    if not LOG_PATH.exists():
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def log_message(message_id: str, raw_message: str, detected_language: str,
                 intent_label: str, entities: dict, confidence: float,
                 outcome: str, vertical: str, client_id: str = "default"):
    _ensure_header()
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow({
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_message": raw_message,
            "detected_language": detected_language,
            "intent_label": intent_label,
            "entities": entities,
            "confidence": confidence,
            "outcome": outcome,
            "vertical": vertical,
            "client_id": client_id,
        })
