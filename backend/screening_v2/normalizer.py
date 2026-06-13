from __future__ import annotations
import re
import jellyfish
from unidecode import unidecode
from .models import NormalizedInput

LEGAL_SUFFIXES = {
    "llc", "ltd", "gmbh", "doo", "inc", "corp", "sa", "bv",
    "jsc", "ojsc", "pjsc", "holdings", "holding", "group",
    "trading", "company", "international", "enterprises",
    "services", "limited", "incorporated", "ag", "plc", "nv",
    "srl", "spa", "oy", "ab", "as",
}

PATRONYM_SUFFIXES = (
    "ovich", "evich", "ievich", "ovna", "evna", "ievna",
    "ich", "vna", "itch", "witch",
)

ABBREVIATIONS: dict[str, str] = {
    "vtb": "vneshtorgbank",
    "veb": "vnesheconombank",
}


def _to_ascii(text: str) -> str:
    if text.isascii():
        return text
    return unidecode(text)


class Normalizer:
    def detect_type(self, name: str) -> str:
        tokens = set(re.sub(r"[^\w\s]", " ", name.lower()).split())
        if tokens & LEGAL_SUFFIXES:
            return "entity"
        return "individual"

    def normalize(self, name: str, entity_type: str) -> NormalizedInput:
        if entity_type == "auto":
            entity_type = self.detect_type(name)
        if entity_type == "individual":
            return self._normalize_individual(name)
        return self._normalize_entity(name)

    def _normalize_individual(self, name: str) -> NormalizedInput:
        cleaned = re.sub(r"[^\w\s]", " ", name).strip()
        cleaned = _to_ascii(cleaned).lower()
        tokens = [
            t for t in cleaned.split()
            if not (len(t) > 9 and t.endswith(PATRONYM_SUFFIXES))
        ]
        cleaned = " ".join(tokens)
        phonetic = jellyfish.nysiis(cleaned) if cleaned else None
        return NormalizedInput(raw=name, cleaned=cleaned, phonetic=phonetic, entity_type="individual")

    def _normalize_entity(self, name: str) -> NormalizedInput:
        cleaned = re.sub(r"[^\w\s]", " ", name).strip()
        cleaned = _to_ascii(cleaned).lower()
        tokens = [t for t in cleaned.split() if t not in LEGAL_SUFFIXES]
        cleaned = " ".join(tokens)
        cleaned = ABBREVIATIONS.get(cleaned, cleaned)
        return NormalizedInput(raw=name, cleaned=cleaned, phonetic=None, entity_type="entity")
