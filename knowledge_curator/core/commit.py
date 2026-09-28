"""Document commit coordinator (docs/03 §5.4 atomic ingest & version snapshot).

Atomic visibility model (not fake cross-store ACID):

    PREPARING
      -> STRUCTURAL_STAGED
      -> STRUCTURAL_COMMITTED
      -> VECTOR_PENDING / VECTOR_COMMITTED
      -> SNAPSHOT_CREATED
      -> PUBLISHED

* transaction boundary = one document
* vector failure after structural commit -> pending_vector (recoverable)
* pending_vector must not publish a KB version
* replay must not duplicate structural records
* idempotency key = (ref_id, source_fingerprint)
* snapshot manifest is deterministic
* rollback only moves the visible version pointer
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Optional

from knowledge_curator.ports.document_commit_store import DocumentCommitRecord, DocumentCommitStore
from knowledge_curator.ports.usdo_store import USDOStore
from knowledge_curator.ports.vector_index import VectorIndex
from knowledge_curator.ports.version_store import VersionStore
from knowledge_curator.schemas.assertions import Assertion, AssertionSet, Confidence
from knowledge_curator.schemas.commit import (
    AdmittedAssertion,
    AssertionVisibility,
    CommitPhase,
    CommitRequest,
    CommitResult,
    CommitStatus,
    SnapshotManifest,
    SourceIdentity,
    USDORecord,
    VectorPayload,
)
from knowledge_curator.schemas.curation import CurationAction, CurationReport


class DocumentCommitCoordinator:
    """Coordinate structural + vector + USDO + snapshot publish for one document.

    Args:
        commit_store: Idempotent document commit lifecycle store.
        vector_index: Vector upsert port.
        usdo_store: USDO/payload registration port.
        version_store: Snapshot/version publish and rollback port.
    """

    def __init__(
        self,
        commit_store: DocumentCommitStore,
        vector_index: VectorIndex,
        usdo_store: USDOStore,
        version_store: VersionStore,
    ) -> None:
        self._commits = commit_store
        self._vectors = vector_index
        self._usdo = usdo_store
        self._versions = version_store

    async def commit(self, request: CommitRequest) -> CommitResult:
        """Commit one curated document (or replay/idempotent-hit).

        Args:
            request: Source identity + AssertionSet + CurationReport.

        Returns:
            CommitResult describing publish / pending_vector / idempotent hit.
        """
        ref_id = request.source.ref_id
        fingerprint = request.source.source_fingerprint

        existing = self._commits.find_by_key(ref_id, fingerprint)
        if existing is not None:
            return self._resume_existing(existing)

        eligibility = self._eligibility(request.report)
        if not eligibility["publishable"]:
            return CommitResult(
                status=CommitStatus.NOT_PUBLISHABLE,
                commit_id="",
                phase=CommitPhase.FAILED,
                warnings=eligibility["warnings"],
                detail={"reason": eligibility["reason"]},
            )

        record = DocumentCommitRecord(
            commit_id=f"dc-{uuid.uuid4().hex[:12]}",
            ref_id=ref_id,
            source_fingerprint=fingerprint,
            phase=CommitPhase.PREPARING,
        )
        self._commits.create(record)

        try:
            admitted = self._admit_assertions(request)
            usdo_records = self._build_usdo(request)
            vector_payloads = self._build_vectors(request, admitted)
            metadata_hash = self._hash_metadata(request)

            record.admitted = admitted
            record.usdo_records = usdo_records
            record.vector_payloads = vector_payloads
            record.metadata_hash = metadata_hash
            record.phase = CommitPhase.STRUCTURAL_STAGED
            self._commits.update(record)

            # Structural registration (staged then committed as one document unit)
            self._usdo.register(usdo_records)
            record.phase = CommitPhase.STRUCTURAL_COMMITTED
            self._commits.update(record)
        except Exception as exc:  # pre-publish failure -> rollback staged state
            record.phase = CommitPhase.FAILED
            record.error = str(exc)
            self._commits.update(record)
            return CommitResult(
                status=CommitStatus.FAILED,
                commit_id=record.commit_id,
                phase=CommitPhase.FAILED,
                warnings=["structural stage failed; no version published"],
                detail={"error": str(exc)},
            )

        return self._write_vectors_and_publish(record)

    def _resume_existing(self, record: DocumentCommitRecord) -> CommitResult:
        """Replay or return existing result without duplicating structural records."""
        if record.phase == CommitPhase.PUBLISHED and record.version_id:
            return CommitResult(
                status=CommitStatus.IDEMPOTENT_HIT,
                commit_id=record.commit_id,
                phase=record.phase,
                snapshot_id=record.snapshot_id,
                version_id=record.version_id,
                warnings=["exact (ref_id, source_fingerprint) already published"],
                detail={"idempotent": True},
            )

        if record.phase in (
            CommitPhase.STRUCTURAL_COMMITTED,
            CommitPhase.VECTOR_PENDING,
            CommitPhase.VECTOR_COMMITTED,
            CommitPhase.SNAPSHOT_CREATED,
        ):
            # Replay: structural records already exist; only retry vector/publish.
            before = self._commits.count_structural_assertions(record.commit_id)
            result = self._write_vectors_and_publish(record)
            after = self._commits.count_structural_assertions(record.commit_id)
            if after != before:
                raise RuntimeError("replay duplicated structural assertion records")
            return result

        return CommitResult(
            status=CommitStatus.FAILED,
            commit_id=record.commit_id,
            phase=record.phase,
            warnings=["existing commit is not resumable"],
            detail={"error": record.error or "not resumable"},
        )

    def _write_vectors_and_publish(self, record: DocumentCommitRecord) -> CommitResult:
        """Vector upsert + snapshot + single version publish with compensation."""
        # Vector write (two-phase / compensation: structural already committed)
        if record.phase in (
            CommitPhase.STRUCTURAL_COMMITTED,
            CommitPhase.VECTOR_PENDING,
        ):
            try:
                self._vectors.upsert(record.vector_payloads)
                record.phase = CommitPhase.VECTOR_COMMITTED
                self._commits.update(record)
            except Exception as exc:
                record.phase = CommitPhase.VECTOR_PENDING
                record.error = str(exc)
                self._commits.update(record)
                return CommitResult(
                    status=CommitStatus.PENDING_VECTOR,
                    commit_id=record.commit_id,
                    phase=CommitPhase.VECTOR_PENDING,
                    warnings=[
                        "vector upsert failed; structural committed; pending_vector",
                        "no KB version published while pending",
                    ],
                    detail={"error": str(exc), "recoverable": True},
                )

        # Deterministic snapshot manifest
        if record.phase == CommitPhase.VECTOR_COMMITTED:
            manifest = self._build_manifest(record)
            record.manifest = manifest
            try:
                snapshot = self._versions.create_snapshot(manifest)
                record.snapshot_id = snapshot.snapshot_id
                record.phase = CommitPhase.SNAPSHOT_CREATED
                self._commits.update(record)
            except Exception as exc:
                record.phase = CommitPhase.VECTOR_PENDING
                record.error = str(exc)
                self._commits.update(record)
                return CommitResult(
                    status=CommitStatus.PENDING_VECTOR,
                    commit_id=record.commit_id,
                    phase=CommitPhase.VECTOR_PENDING,
                    warnings=["snapshot creation failed; recoverable"],
                    detail={"error": str(exc), "recoverable": True},
                )

        # Publish exactly one KB version
        if record.phase == CommitPhase.SNAPSHOT_CREATED and record.snapshot_id:
            version = self._versions.publish_version(record.snapshot_id)
            record.version_id = version.version_id
            record.phase = CommitPhase.PUBLISHED
            record.error = None
            self._commits.update(record)
            return CommitResult(
                status=CommitStatus.PUBLISHED,
                commit_id=record.commit_id,
                phase=CommitPhase.PUBLISHED,
                snapshot_id=record.snapshot_id,
                version_id=record.version_id,
                warnings=["published one KB version for document commit"],
            )

        return CommitResult(
            status=CommitStatus.FAILED,
            commit_id=record.commit_id,
            phase=record.phase,
            warnings=["unexpected phase in publish path"],
            detail={"phase": record.phase.value},
        )

    # ------------------------------------------------------------------
    # Eligibility (03 §5.4 + plan §4)
    # ------------------------------------------------------------------

    def _eligibility(self, report: CurationReport) -> dict[str, Any]:
        warnings: list[str] = []
        if report.returned_upstream_count > 0 or report.status == "return_upstream":
            return {
                "publishable": False,
                "reason": "return_upstream document cannot publish",
                "warnings": ["RETURN_UPSTREAM -> not publishable"],
            }
        actions = [d.action for d in report.decisions]
        if not actions:
            return {
                "publishable": False,
                "reason": "no assertion decisions",
                "warnings": ["empty report is not publishable"],
            }
        if all(a == CurationAction.REJECT for a in actions):
            return {
                "publishable": False,
                "reason": "all assertions rejected",
                "warnings": ["all-rejected document is not publishable"],
            }
        return {"publishable": True, "reason": "", "warnings": warnings}

    def _admit_assertions(self, request: CommitRequest) -> list[AdmittedAssertion]:
        decision_by_id = {d.assertion_id: d for d in request.report.decisions}
        admitted: list[AdmittedAssertion] = []
        for assertion in request.assertion_set.assertions:
            decision = decision_by_id.get(assertion.id)
            if decision is None:
                continue
            if decision.action == CurationAction.REJECT:
                continue
            if decision.action == CurationAction.RETURN_UPSTREAM:
                continue
            if decision.action == CurationAction.DOWNGRADE:
                admitted.append(
                    AdmittedAssertion(
                        assertion=assertion,
                        visibility=AssertionVisibility.DOWNGRADED,
                        confidence=decision.confidence,
                        action=decision.action,
                    )
                )
                continue
            if decision.action == CurationAction.PENDING_REVIEW:
                admitted.append(
                    AdmittedAssertion(
                        assertion=assertion,
                        visibility=AssertionVisibility.PENDING,
                        confidence=decision.confidence,
                        action=decision.action,
                    )
                )
                continue
            # ACCEPT (and SUPERSEDE treated as active for Phase 2 mechanical publish)
            admitted.append(
                AdmittedAssertion(
                    assertion=assertion,
                    visibility=AssertionVisibility.ACTIVE,
                    confidence=decision.confidence,
                    action=decision.action,
                )
            )
        return admitted

    def _build_usdo(self, request: CommitRequest) -> list[USDORecord]:
        content_hash = self._hash_json(
            {
                "ref_id": request.source.ref_id,
                "fingerprint": request.source.source_fingerprint,
                "assertion_ids": sorted(a.id for a in request.assertion_set.assertions),
            }
        )
        return [
            USDORecord(
                record_id=f"usdo-{request.source.ref_id}-{request.source.source_fingerprint[:12]}",
                ref_id=request.source.ref_id,
                content_hash=content_hash,
                payload_kind="usdo_json",
            )
        ]

    def _build_vectors(
        self,
        request: CommitRequest,
        admitted: list[AdmittedAssertion],
    ) -> list[VectorPayload]:
        payloads: list[VectorPayload] = []
        for item in admitted:
            payloads.append(
                VectorPayload(
                    vector_id=f"vec-{request.source.ref_id}-{item.assertion.id}",
                    ref_id=request.source.ref_id,
                    assertion_id=item.assertion.id,
                    content_hash=self._hash_assertion(item.assertion),
                )
            )
        return payloads

    def _hash_metadata(self, request: CommitRequest) -> str:
        meta = request.assertion_set.metadata
        return self._hash_json(
            {
                "title": meta.title,
                "authors": list(meta.authors),
                "year": meta.year,
                "source": meta.source,
                "doi": meta.doi,
                "stable_id": meta.stable_id,
            }
        )

    def _build_manifest(self, record: DocumentCommitRecord) -> SnapshotManifest:
        manifest = SnapshotManifest(
            ref_id=record.ref_id,
            source_fingerprint=record.source_fingerprint,
            assertion_hashes=[self._hash_assertion(a.assertion) for a in record.admitted],
            usdo_hashes=[u.content_hash for u in record.usdo_records],
            vector_ids=[v.vector_id for v in record.vector_payloads],
            metadata_hash=record.metadata_hash,
            decision_hashes=[
                self._hash_json(
                    {
                        "assertion_id": a.assertion.id,
                        "action": a.action.value,
                        "confidence": a.confidence.value,
                        "visibility": a.visibility.value,
                    }
                )
                for a in record.admitted
            ],
        )
        manifest.content_hash = self._hash_json(manifest.stable_payload())
        return manifest

    def _hash_assertion(self, assertion: Assertion) -> str:
        return self._hash_json(
            {
                "id": assertion.id,
                "ref_id": assertion.ref_id,
                "subject": assertion.subject.resolved_entity,
                "property": assertion.property,
                "value": assertion.object.value,
                "unit": assertion.object.unit,
                "value_type": assertion.object.value_type.value,
                "conditions": [
                    {"c": c.eddo_class, "v": c.value, "u": c.unit} for c in assertion.conditions
                ],
                "locator": assertion.provenance.locator if assertion.provenance else None,
                "claim_type": assertion.claim_type.value,
                "origin": assertion.source_claim_origin.value,
            }
        )

    @staticmethod
    def _hash_json(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
