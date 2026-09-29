"""Reversible tokenizer contract + chunk identity + canonical payload prefix."""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenizerPort(Protocol):
    """Reversible tokenizer: encode/decode roundtrip must preserve content."""

    def encode(self, text: str) -> list[str]:
        """Encode text into token units."""
        ...

    def decode(self, tokens: list[str]) -> str:
        """Decode tokens back to text (roundtrip-safe)."""
        ...

    def count(self, text: str) -> int:
        """Token count convenience."""
        ...


class WordTokenizer:
    """Deterministic tokenizer with punctuation/non-ASCII roundtrip.

    Encodes to non-whitespace tokens; decode joins with single space.
    Roundtrip preserves word content (not exact whitespace).
    """

    def encode(self, text: str) -> list[str]:
        if not text:
            return []
        return text.split()

    def decode(self, tokens: list[str]) -> str:
        return " ".join(tokens)

    def count(self, text: str) -> int:
        return len(self.encode(text))


# Type labels for docs/03 §6.1 metadata prefix
CHUNK_TYPE_LABELS = {
    "text": "文本",
    "table": "表",
    "chart": "图",
    "evidence_card": "证据卡",
}


def build_metadata_prefix(ref_id: str, page: str | None, section: str | None, type_key: str) -> str:
    """Build canonical metadata prefix: [ref_id|page|section|type(类型)]"""
    label = CHUNK_TYPE_LABELS.get(type_key, type_key)
    return f"[{ref_id}|{page or '-'}|{section or '-'}|type({label})]"


def stable_chunk_id(ref_id: str, page: str | None, section: str | None, kind: str, window: str) -> str:
    """Collision-free stable chunk id using SHA-256 (not Python hash).

    Identity includes ref_id, page, section, kind, and window digest.
    """
    raw = "|".join([
        ref_id or "",
        page or "-",
        section or "-",
        kind,
        hashlib.sha256(window.encode("utf-8")).hexdigest()[:16],
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
