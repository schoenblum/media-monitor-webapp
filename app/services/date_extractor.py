"""Best-effort publication-date extraction from a Google CSE snippet (ported from v38a)."""
import re

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

_DATE_PATTERNS = [
    (
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        "MDY",
    ),
    (
        r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(\d{4})\b",
        "DMY",
    ),
    (r"\b(\d{4})-(\d{2})-(\d{2})\b", "ISO"),
    (r"\b(\d{4})/(\d{2})/(\d{2})\b", "ISO"),
]


def extract_date(snippet: str | None) -> str:
    """Return a `YYYY/MM/DD` date if one can be parsed from the snippet, else ''."""
    if not snippet:
        return ""
    for pattern, fmt in _DATE_PATTERNS:
        m = re.search(pattern, snippet, re.IGNORECASE)
        if not m:
            continue
        try:
            if fmt == "ISO":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif fmt == "DMY":
                d = int(m.group(1))
                mo = _MONTH_MAP.get(m.group(2).lower(), 0)
                y = int(m.group(3))
            else:  # MDY
                mo = _MONTH_MAP.get(m.group(1).lower(), 0)
                d = int(m.group(2))
                y = int(m.group(3))
            if mo and 1 <= d <= 31 and 1900 <= y <= 2100:
                return f"{y}/{mo:02d}/{d:02d}"
        except (ValueError, AttributeError):
            continue
    return ""
