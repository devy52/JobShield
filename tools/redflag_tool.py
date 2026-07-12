RED_FLAG_PATTERNS = {
    "upfront_payment": [
        "processing fee",
        "registration fee",
        "pay for training",
        "purchase your own equipment",
        "activation fee",
        "send payment to",
        "training fee",
    ],
    "no_interview": [
        "no interview required",
        "no interview needed",
        "immediate start",
        "hired instantly",
    ],
    "check_reshipping": [
        "deposit this check",
        "cash this check",
        "reship",
        "forward the package",
        "money order",
    ],
    "off_platform_pressure": [
        "contact us on whatsapp",
        "message us on telegram",
        "text me directly",
        "personal gmail",
    ],
    "urgency_pressure": [
        "act now",
        "limited spots",
        "offer expires today",
        "respond within 24 hours",
    ],
}


def scan_red_flags(raw_text: str) -> dict:
    """Cheap deterministic backstop -- runs before/alongside the LLM tools, no network needed."""
    text_lower = (raw_text or "").lower()
    hits = {}
    for category, phrases in RED_FLAG_PATTERNS.items():
        matched = [p for p in phrases if p in text_lower]
        if matched:
            hits[category] = matched

    return {
        "categories_triggered": list(hits.keys()),
        "matches": hits,
        "total_hits": sum(len(v) for v in hits.values()),
    }
