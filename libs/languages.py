"""Language helpers: detection and expected translation length between languages."""
import re

# Approximate text length (chars) of a text in each language, relative to the same text in English
LENGTH_FACTORS = {
    "en": 1.0,
    "fr": 1.15,
    "de": 1.2,
    "es": 1.15,
    "it": 1.1,
    "pt": 1.1,
    "ja": 0.5,
    "zh": 0.35,
}

# Frequent short words used to guess the language of a Latin-script text
STOPWORDS = {
    "en": {"the", "and", "of", "to", "is", "that", "with", "for", "this", "which"},
    "fr": {"le", "la", "les", "et", "des", "du", "une", "est", "que", "dans"},
    "de": {"der", "die", "und", "das", "ist", "nicht", "mit", "den", "ein", "zu"},
    "es": {"el", "los", "las", "y", "que", "del", "una", "por", "con", "para"},
    "it": {"il", "di", "che", "e", "gli", "della", "una", "per", "non", "sono"},
    "pt": {"o", "os", "que", "do", "da", "uma", "em", "não", "com", "para"},
}


def detect_language(text: str) -> str | None:
    """Guess the ISO code of the language of a text, None when unsure."""
    sample = text[:20000]
    if not sample.strip():
        return None
    if re.search(r'[぀-ヿ]', sample):
        return "ja"
    cjk = len(re.findall(r'[一-鿿]', sample))
    if cjk > len(sample) * 0.2:
        return "zh"
    words = re.findall(r"[a-zà-ÿ]+", sample.lower())
    if not words:
        return None
    scores = {lang: sum(1 for w in words if w in stop) for lang, stop in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    # Require a clear signal: stopwords are frequent in any real text
    return best if scores[best] >= len(words) * 0.05 else None


def expected_length_ratio(source_lang: str | None, target_lang: str | None) -> float | None:
    """Expected translated/source text length ratio, None when a language is unknown."""
    if source_lang not in LENGTH_FACTORS or target_lang not in LENGTH_FACTORS:
        return None
    return LENGTH_FACTORS[target_lang] / LENGTH_FACTORS[source_lang]
