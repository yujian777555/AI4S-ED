"""EvidenceMetadataPort adapter bound to the CURRENT retrieval set (Phase 4.3).

H1 retrieval-set binding: a claim cannot cite a KB reference that was not
returned by this retrieval pass, even if the ref exists elsewhere in the KB.
"""

from __future__ import annotations

from typing import Optional

from knowledge_curator.ports.evidence_store import RefMetadata
from knowledge_curator.retrieval.evidence_models import RetrievalEvidenceRecord


class RetrievalSetMetadata:
    """EvidenceMetadataPort over a single EvidenceBundle retrieval set.

    - ref_exists: True only when some retrieved record carries that ref_id.
    - anchor_exists: True only when (ref_id, locator) is present in the
      current retrieval set. Unknown ref -> False. Ref present but locator
      not indexed in this set -> False (not in current set).
    """

    def __init__(
        self,
        records: list[RetrievalEvidenceRecord],
        ref_metadata: Optional[dict[str, RefMetadata]] = None,
    ) -> None:
        self._records = list(records)
        self._ref_meta = dict(ref_metadata or {})
        self._refs: set[str] = {r.ref_id for r in self._records}
        self._pairs: set[tuple[str, str]] = set()
        for r in self._records:
            if r.locator:
                self._pairs.add((r.ref_id, r.locator.strip()))

    def ref_exists(self, ref_id: str) -> bool:
        return ref_id in self._refs

    def get_ref_metadata(self, ref_id: str) -> Optional[RefMetadata]:
        if ref_id in self._ref_meta:
            return self._ref_meta[ref_id]
        if self.ref_exists(ref_id):
            return RefMetadata(ref_id=ref_id)
        return None

    def anchor_exists(self, ref_id: str, locator: str) -> Optional[bool]:
        if not locator or not locator.strip():
            return False
        if not self.ref_exists(ref_id):
            return False
        return (ref_id, locator.strip()) in self._pairs
