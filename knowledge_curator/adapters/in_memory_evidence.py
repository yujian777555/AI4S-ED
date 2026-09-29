"""InMemory EvidenceMetadataPort adapter for tests only."""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.evidence_store import RefMetadata


class InMemoryEvidenceStore:
    """Test-only in-memory evidence metadata lookup."""

    def __init__(self, refs: Optional[dict[str, RefMetadata]] = None) -> None:
        self._refs: dict[str, RefMetadata] = dict(refs or {})

    def ref_exists(self, ref_id: str) -> bool:
        return ref_id in self._refs

    def get_ref_metadata(self, ref_id: str) -> Optional[RefMetadata]:
        return self._refs.get(ref_id)

    def anchor_exists(self, ref_id: str, locator: str) -> bool:
        return self.ref_exists(ref_id) and bool(locator and locator.strip())

    def add_ref(self, ref_id: str, **kwargs) -> None:
        self._refs[ref_id] = RefMetadata(ref_id=ref_id, **kwargs)
