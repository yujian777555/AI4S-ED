"""Reversible tokenizer contract (Phase 4.1.3: format-preserving, token-window)."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenizerPort(Protocol):
    """Reversible tokenizer: decode(encode(text)) == text.

    Window unit and budget unit are the same: encode() tokens.
    """

    def encode(self, text: str) -> list[str]:
        ...

    def decode(self, tokens: list[str]) -> str:
        ...

    def count(self, text: str) -> int:
        ...


class WordTokenizer:
    """Lossless format-preserving tokenizer.

    Encodes whitespace runs and lexical units as separate tokens so
    decode(encode(text)) reconstructs spaces, newlines, punctuation exactly.
    count(text) == len(encode(text)) for budget consistency.
    """

    def encode(self, text: str) -> list[str]:
        if not text:
            return []
        return re.findall(r"\s+|\S+", text)

    def decode(self, tokens: list[str]) -> str:
        return "".join(tokens)

    def count(self, text: str) -> int:
        return len(self.encode(text))


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
