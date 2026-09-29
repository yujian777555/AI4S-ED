"""Reversible tokenizer contract (Phase 4.1.2: truly lossless roundtrip)."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenizerPort(Protocol):
    """Reversible tokenizer: decode(encode(text)) == text must hold."""

    def encode(self, text: str) -> list[str]:
        ...

    def decode(self, tokens: list[str]) -> str:
        ...

    def count(self, text: str) -> int:
        ...


class WordTokenizer:
    """Deterministic lossless tokenizer.

    Splits into whitespace and non-whitespace runs so decode(encode(text))
    exactly reconstructs the original, including spaces and newlines.
    """

    def encode(self, text: str) -> list[str]:
        if not text:
            return []
        return re.findall(r"\s+|\S+", text)

    def decode(self, tokens: list[str]) -> str:
        return "".join(tokens)

    def count(self, text: str) -> int:
        # Non-whitespace token units for budget purposes
        return len([t for t in self.encode(text) if t.strip()])


CHUNK_TYPE_LABELS = {
    "text": "文本",
    "table": "表",
    "chart": "图",
    "evidence_card": "证据卡",
}


def build_metadata_prefix(ref_id: str, page: str | None, section: str | None, type_key: str) -> str:
    label = CHUNK_TYPE_LABELS.get(type_key, type_key)
    return f"[{ref_id}|{page or '-'}|{section or '-'}|type({label})]"


def stable_chunk_id(ref_id: str, page: str | None, section: str | None, kind: str, window: str) -> str:
    raw = "|".join([
        ref_id or "",
        page or "-",
        section or "-",
        kind,
        hashlib.sha256(window.encode("utf-8")).hexdigest()[:16],
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
