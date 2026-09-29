"""EvidenceMetadataPort — KB metadata lookup boundary for §6.

Runtime-independent. No SQLite/FAISS/HTTP hard-coding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass
class RefMetadata:
    """Minimal ref metadata for H2 local existence checks."""

    ref_id: str
    title: Optional[str] = None
    doi: Optional[str] = None
    year: Optional[int] = None


@runtime_checkable
class EvidenceMetadataPort(Protocol):
    """KB metadata lookup for evidence/anchor validation."""

    def ref_exists(self, ref_id: str) -> bool:
        """True when the cited reference exists in KB metadata."""
        ...

    def get_ref_metadata(self, ref_id: str) -> Optional[RefMetadata]:
        """Return stored metadata when locally available."""
        ...

    def anchor_exists(self, ref_id: str, locator: str) -> bool:
        """True when the anchor (ref_id, locator) is supported where possible."""
        ...
