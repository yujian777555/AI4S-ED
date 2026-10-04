"""SI-4-R6 qualification provider fixture.

Test-only. Seeds revision state for native §7 qualification.
Exposed only via AI4S_SYSTEM_ADAPTER_FACTORY env.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from integration.system.fixtures.si2b_provider import (
    TestFailureInjection,
    _StubOntology,
    _StubRepository,
    _StubValidator,
    _TestCommitStore,
    _TestEventOutbox,
    _TestLifecycleStore,
    _TestRevisionPublicationStore,
    _TestSourceVersionRegistry,
    _TestStructuralStore,
    _TestUSDOStore,
    _TestVectorIndex,
    _TestVersionStore,
)


def create_r6_provider_bundle() -> dict:
    """Provider bundle with seeded revision state for qualification."""
    fail = TestFailureInjection()

    commit_store = _TestCommitStore(fail)
    structural_store = _TestStructuralStore(fail)
    vector_index = _TestVectorIndex(fail)
    usdo_store = _TestUSDOStore(fail)
    version_store = _TestVersionStore(fail)
    source_registry = _TestSourceVersionRegistry(fail)
    lifecycle_store = _TestLifecycleStore(fail)
    event_outbox = _TestEventOutbox(fail)
    publication_store = _TestRevisionPublicationStore(fail)

    # Seed prior revision state
    from knowledge_curator.schemas.source_versions import (
        SourceKind, SourceVersionRecord, VersionRelation, WorkRecord,
    )
    from knowledge_curator.schemas.commit import SnapshotManifest

    source_registry.append_work(WorkRecord(work_id="w-r6", created_evidence="r6-qualification"))

    prior_manifest = SnapshotManifest(
        ref_id="ED-PRIOR", source_fingerprint="fp-prior-r6",
        assertion_hashes=["h-prior"], usdo_hashes=["u-prior"], vector_ids=["v-prior"],
        metadata_hash="m-prior", decision_hashes=["d-prior"],
    )
    prior_manifest.content_hash = "r6-prior-content-hash"
    prior_snap = version_store.create_snapshot(prior_manifest)
    prior_ver = version_store.publish_version(prior_snap.snapshot_id)

    source_registry.append_source_version(SourceVersionRecord(
        source_version_id="sv-prior-r6", work_id="w-r6", ref_id="ED-PRIOR",
        source_fingerprint="fp-prior-r6", source_kind=SourceKind.PREPRINT,
        relation=VersionRelation.NONE, prior_source_version_id=None,
    ))
    source_registry.bind_source_version("sv-prior-r6", prior_ver.version_id, prior_snap.snapshot_id)

    source_registry.append_source_version(SourceVersionRecord(
        source_version_id="sv-new-r6", work_id="w-r6", ref_id="ED-NEW",
        source_fingerprint="fp-new-r6", source_kind=SourceKind.JOURNAL,
        relation=VersionRelation.PREPRINT_TO_JOURNAL, prior_source_version_id="sv-prior-r6",
    ))

    return {
        "curator": {
            "repository": _StubRepository(),
            "ontology": _StubOntology(),
            "mechanism_validator": _StubValidator(),
            "provider_identity": "r6-qualification-provider",
        },
        "commit": {
            "commit_store": commit_store,
            "structural_store": structural_store,
            "vector_index": vector_index,
            "usdo_store": usdo_store,
            "version_store": version_store,
            "provider_identity": "r6-qualification-provider",
        },
        "revision": {
            "source_registry": source_registry,
            "lifecycle_store": lifecycle_store,
            "event_outbox": event_outbox,
            "publication_store": publication_store,
            "provider_identity": "r6-qualification-provider",
        },
    }
