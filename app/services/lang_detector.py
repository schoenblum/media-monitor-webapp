"""Language detection wrapper — falls back to 'unknown' on short text or detector failure."""
from langdetect import DetectorFactory, LangDetectException, detect

# Deterministic detection across runs.
DetectorFactory.seed = 0

LANG_NAMES: dict[str, str] = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "zh-tw": "Chinese",
    "ko": "Korean",
    "ja": "Japanese",
    "ar": "Arabic",
    "tr": "Turkish",
    "id": "Indonesian",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
    "nl": "Dutch",
    "sv": "Swedish",
}


def detect_language(title: str | None, snippet: str | None) -> tuple[str, str]:
    """Return ``(language_code, language_name)`` — ``('unknown', '?')`` if not detectable."""
    text = ((title or "") + " " + (snippet or "")).strip()
    if len(text) < 20:
        return "unknown", "?"
    try:
        code = detect(text)
        return code, LANG_NAMES.get(code, code)
    except LangDetectException:
        return "unknown", "?"
