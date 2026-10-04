"""InMemory EvidenceMetadataPort adapter for tests only.

Supports real locator registration per ref (Phase 4.0.1).
"""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.evidence_store import RefMetadata


class InMemoryEvidenceStore:
    """Test-only in-memory evidence metadata lookup with locator index."""

    def __init__(
        self,
        refs: Optional[dict[str, RefMetadata]] = None,
        locators: Optional[dict[str, set[str]]] = None,
    ) -> None:
        self._refs: dict[str, RefMetadata] = dict(refs or {})
        self._locators: dict[str, set[str]] = {k: set(v) for k, v in (locators or {}).items()}

    def ref_exists(self, ref_id: str) -> bool:
        return ref_id in self._refs

    def get_ref_metadata(self, ref_id: str) -> Optional[RefMetadata]:
        return self._refs.get(ref_id)

    def anchor_exists(self, ref_id: str, locator: str) -> Optional[bool]:
        if not self.ref_exists(ref_id):
            return False
        if not locator or not locator.strip():
            return False
        known = self._locators.get(ref_id)
        if known is None:
            # No locator index for this ref — cannot verify
            return None
        return locator.strip() in known

    def add_ref(self, ref_id: str, locators: Optional[set[str]] = None, **kwargs) -> None:
        self._refs[ref_id] = RefMetadata(ref_id=ref_id, **kwargs)
        if locators is not None:
            self._locators[ref_id] = set(locators)

    def add_locator(self, ref_id: str, locator: str) -> None:
        self._locators.setdefault(ref_id, set()).add(locator)
