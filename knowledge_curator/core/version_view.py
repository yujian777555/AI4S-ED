"""Version-scoped storage read view (03 §5.4 storage/version resolution).

Not §6 retrieval/RAG. Resolves exactly the immutable storage dependencies
of one snapshot/version so rollback is semantically reproducible (P2.2-04).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from knowledge_curator.ports.structural_store import StructuralDocumentRecord, StructuralKnowledgeStore
from knowledge_curator.ports.usdo_store import USDOStore
from knowledge_curator.ports.vector_index import VectorIndex
from knowledge_curator.ports.version_store import SnapshotRecord, VersionRecord, VersionStore
from knowledge_curator.schemas.commit import SnapshotManifest, USDORecord, VectorPayload


@dataclass
class ResolvedKnowledgeBundle:
    """Exact storage dependencies of one published version/snapshot."""

    version_id: str
    snapshot_id: str
    manifest: Optional[SnapshotManifest]
    structural: Optional[StructuralDocumentRecord]
    usdo_records: list[USDORecord] = field(default_factory=list)
    vector_payloads: list[VectorPayload] = field(default_factory=list)


class VersionedKnowledgeView:
    """Resolve structural/USDO/vector dependencies for a version or current pointer.

    After rollback_to(V1), resolve(None) must return V1 dependencies.
    resolve(V2) must still return historical V2 dependencies.
    """

    def __init__(
        self,
        version_store: VersionStore,
        structural_store: StructuralKnowledgeStore,
        usdo_store: USDOStore,
        vector_index: VectorIndex,
    ) -> None:
        self._versions = version_store
        self._structural = structural_store
        self._usdo = usdo_store
        self._vectors = vector_index

    def resolve(self, version_id: Optional[str] = None) -> Optional[ResolvedKnowledgeBundle]:
        """Resolve dependencies for an explicit version_id, or the current version."""
        if version_id is None:
            version = self._versions.current_version()
        else:
            version = self._versions.get_version(version_id)
        if version is None or not version.published:
            return None

        snapshot = self._versions.get_snapshot(version.snapshot_id)
        manifest = snapshot.manifest if snapshot else None

        structural = None
        usdo_records: list[USDORecord] = []
        vector_payloads: list[VectorPayload] = []

        if manifest is not None:
            if manifest.structural_stage_id:
                structural = self._structural.get_committed(manifest.structural_stage_id)
            for rid in manifest.usdo_record_ids:
                rec = self._usdo.get_by_id(rid)
                if rec is not None:
                    usdo_records.append(rec)
            for vid in manifest.vector_ids:
                payload = self._vectors.get_by_id(vid)
                if payload is not None:
                    vector_payloads.append(payload)

        return ResolvedKnowledgeBundle(
            version_id=version.version_id,
            snapshot_id=version.snapshot_id,
            manifest=manifest,
            structural=structural,
            usdo_records=usdo_records,
            vector_payloads=vector_payloads,
        )

    def resolve_current(self) -> Optional[ResolvedKnowledgeBundle]:
        """Resolve the currently visible version's dependencies."""
        return self.resolve(None)
