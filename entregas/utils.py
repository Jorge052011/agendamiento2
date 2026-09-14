import re


# ── Teléfono ──────────────────────────────────────────────────────────────────

def normalize_phone(raw):
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("0"):
        digits = "56" + digits[1:]
    elif digits.startswith("9") and len(digits) == 9:
        digits = "56" + digits
    return digits
