import re
from typing import Tuple, List

# Regex patterns for different PII categories
PII_PATTERNS = {
    "email": (r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[[EMAIL]]'),
    "phone": (r'\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[[PHONE]]'),
    "ssn": (r'\b\d{3}-\d{2}-\d{4}\b', '[[SSN]]'),
    "card_number": (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[[CARD_NUMBER]]'),
    "address": (r'\b\d+\s+[a-zA-Z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b', '[[ADDRESS]]'),
}

def redact_pii(text: str) -> Tuple[str, List[str]]:
    """
    Scans the given string for PII and replaces it with placeholder tokens.
    Returns the sanitized text and a list of redacted categories.
    """
    if not isinstance(text, str):
        return text, []

    sanitized_text = text
    redacted_categories = set()

    for category, (pattern, token) in PII_PATTERNS.items():
        if re.search(pattern, sanitized_text, re.IGNORECASE):
            sanitized_text = re.sub(pattern, token, sanitized_text, flags=re.IGNORECASE)
            redacted_categories.add(category)

    return sanitized_text, sorted(list(redacted_categories))
