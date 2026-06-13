from __future__ import annotations

import re
import unicodedata

from unidecode import unidecode

# Tokens that add little identity signal in screening.
STOP_TOKENS = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "sir",
    "lord",
    "al",
    "bin",
    "ibn",
    "von",
    "van",
    "de",
    "da",
    "el",
    "the",
    "and",
    "of",
    "company",
    "co",
    "ltd",
    "llc",
    "inc",
    "corp",
    "gmbh",
    "sa",
    "plc",
}

# Very common surnames/given names that inflate false positives.
COMMON_NAME_TOKENS = {
    "kim",
    "lee",
    "chen",
    "wang",
    "li",
    "zhang",
    "liu",
    "mohammed",
    "muhammad",
    "ahmed",
    "ali",
    "hassan",
    "ivan",
    "ivanov",
    "petrov",
    "smith",
    "johnson",
    "brown",
    "garcia",
    "martinez",
    "wagner",
    "muller",
    "schmidt",
}


def normalize_text(value: str) -> str:
    """Lowercase, strip accents, and remove punctuation for comparison."""
    ascii_text = unidecode(value.lower())
    ascii_text = re.sub(r"[^a-z0-9\s]", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def tokenize(value: str, *, drop_stops: bool = True) -> list[str]:
    tokens = [token for token in normalize_text(value).split() if token]
    if not drop_stops:
        return tokens
    return [token for token in tokens if token not in STOP_TOKENS]


def token_sort_key(value: str) -> str:
    tokens = tokenize(value)
    return " ".join(sorted(tokens))


def initials(value: str) -> str:
    return "".join(token[0] for token in tokenize(value) if token)


def is_common_name(value: str) -> bool:
    tokens = tokenize(value)
    if not tokens:
        return False
    common_hits = sum(1 for token in tokens if token in COMMON_NAME_TOKENS)
    return common_hits >= max(1, len(tokens) // 2)


def strip_diacritics(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))
