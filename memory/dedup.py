from __future__ import annotations

import hashlib
import re


def normalize_text(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content.strip().lower())
    return normalized


def build_fingerprint(content: str) -> str:
    return hashlib.sha256(normalize_text(content).encode("utf-8")).hexdigest()


def is_near_duplicate(content_a: str, content_b: str, threshold: float = 0.9) -> bool:
    words_a = set(normalize_text(content_a).split())
    words_b = set(normalize_text(content_b).split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
    return overlap >= threshold
