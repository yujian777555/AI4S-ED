"""Document commit coordinator (docs/03 §5.4 atomic ingest & version snapshot).

Phase 2.2 final atomic visibility & versioned-read closure:
  * structural + USDO finalize is compensatable as a document pair
  * pre-publish failures never leak committed-visible knowledge
  * snapshot create is idempotent by deterministic content hash
  * transient FAILED pre-publish commits are safely restartable
  * PENDING_VECTOR is only for vector recovery; PENDING_FINALIZE for snapshot/publish/ack
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Optional

from knowledge_curator.ports.document_commit_store import DocumentCommitRecord, DocumentCommitStore
from knowledge_curator.ports.structural_store import StructuralDocumentRecord, StructuralKnowledgeStore
from knowledge_curator.ports.usdo_store import USDOStore
from knowledge_curator.ports.vector_index import VectorIndex
from knowledge_curator.ports.version_store import VersionStore
from knowledge_curator.schemas.assertions import Assertion
from knowledge_curator.schemas.commit import (
    AdmittedAssertion,
    AssertionVisibility,
    CommitPhase,
    CommitRequest,
    CommitResult,
    CommitStatus,
    SnapshotManifest,
    USDORecord,
    VectorPayload,
)
from knowledge_curator.schemas.curation import CurationAction, CurationReport


class DocumentCommitCoordinator:
    """Coordinate structural + vector + USDO + snapshot publish for one document."""

    def __init__(
        self,
        commit_store: DocumentCommitStore,
        structural_store: StructuralKnowledgeStore,
        vector_index: VectorIndex,
        usdo_store: USDOStore,
        version_store: VersionStore,
    ) -> None:
        self._commits = commit_store
        self._structural = structural_store
        self._vectors = vector_index
        self._usdo = usdo_store
        self._versions = version_store

    async def commit(self, request: CommitRequest) -> CommitResult:
        """Commit one curated document (or replay/idempotent-hit/safe FAILED retry)."""
        binding_errors = validate_commit_request(request)
        if binding_errors:
            return CommitResult(
                status=CommitStatus.FAILED,
                commit_id="",
                phase=CommitPhase.FAILED,
                warnings=["commit request binding invalid; fail closed"],
                detail={"errors": binding_errors},
            )

        ref_id = request.source.ref_id
        fingerprint = request.source.source_fingerprint

        existing = self._commits.find_by_key(ref_id, fingerprint)
        if existing is not None:
            return self._resume_or_restart(existing, request)

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
        return self._prepare_and_publish(record, request)

    def _resume_or_restart(
        self,
        record: DocumentCommitRecord,
        request: CommitRequest,
    ) -> CommitResult:
        """Resume recoverable states, or restart a transient FAILED pre-publish commit."""
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
            return self._write_vectors_and_publish(record)

        # P2.2-03: transient pre-publish failures (incl. STRUCTURAL_STAGED leftovers
        # after a failed lifecycle ack) are restartable once partial effects are gone.
        if record.phase in (
            CommitPhase.FAILED,
            CommitPhase.PREPARING,
            CommitPhase.STRUCTURAL_STAGED,
        ) and not record.version_id:
            self._compensate_partial(record)
            record.phase = CommitPhase.PREPARING
            record.error = None
            record.snapshot_id = None
            record.admitted = []
            record.usdo_records = []
            record.vector_payloads = []
            try:
                self._commits.update(record)
            except Exception:
                pass
            return self._prepare_and_publish(record, request)

        return CommitResult(
            status=CommitStatus.FAILED,
            commit_id=record.commit_id,
            phase=record.phase,
            warnings=["existing commit is not resumable"],
            detail={"error": record.error or "not resumable"},
        )

    def _prepare_and_publish(
        self,
        record: DocumentCommitRecord,
        request: CommitRequest,
    ) -> CommitResult:
        """Stage + finalize structural/USDO pair, then vector/snapshot/publish."""
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

            self._structural.stage_document(
                StructuralDocumentRecord(
                    ref_id=record.ref_id,
                    source_fingerprint=record.source_fingerprint,
                    stage_id=record.commit_id,
                    assertions=list(admitted),
                    metadata={
                        "title": request.assertion_set.metadata.title,
                        "year": request.assertion_set.metadata.year,
                        "source": request.assertion_set.metadata.source,
                    },
                    metadata_hash=metadata_hash,
                )
            )
            self._usdo.stage(record.commit_id, usdo_records)

            # Finalize pair; compensation runs if either half fails.
            self._structural.commit_stage(record.commit_id)
            self._usdo.commit_stage(record.commit_id)

            record.phase = CommitPhase.STRUCTURAL_COMMITTED
            self._commits.update(record)
        except Exception as exc:
            # Compensate any finalized pair; never leave half-visible knowledge.
            self._compensate_partial(record)
            try:
                self._structural.abort_stage(record.commit_id)
                self._usdo.abort_stage(record.commit_id)
            except Exception:
                pass
            record.phase = CommitPhase.FAILED
            record.error = str(exc)
            try:
                self._commits.update(record)
            except Exception:
                # Lifecycle store may also be failing in this window; local state is enough.
                pass
            return CommitResult(
                status=CommitStatus.FAILED,
                commit_id=record.commit_id,
                phase=CommitPhase.FAILED,
                warnings=[
                    "structural/USDO finalize failed; compensated committed side effects",
                    "no committed-visible knowledge leaked",
                ],
                detail={"error": str(exc), "retryable": True},
            )

        return self._write_vectors_and_publish(record)

    def _compensate_partial(self, record: DocumentCommitRecord) -> None:
        """Undo any committed-visible structural/USDO for an unpublished document."""
        for op in (self._structural.compensate_committed, self._usdo.compensate_committed):
            try:
                op(record.commit_id)
            except Exception:
                pass

    def _write_vectors_and_publish(self, record: DocumentCommitRecord) -> CommitResult:
        """Vector upsert + snapshot + idempotent version publish."""
        if record.phase in (CommitPhase.STRUCTURAL_COMMITTED, CommitPhase.VECTOR_PENDING):
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

        if record.phase == CommitPhase.VECTOR_COMMITTED:
            manifest = self._build_manifest(record)
            record.manifest = manifest
            try:
                snapshot = self._versions.create_snapshot(manifest)
                record.snapshot_id = snapshot.snapshot_id
                record.phase = CommitPhase.SNAPSHOT_CREATED
                self._commits.update(record)
            except Exception as exc:
                # Even if the snapshot side effect landed, report pending_finalize so
                # the caller retries; retry reuses the same snapshot by content hash.
                recovered = None
                if manifest.content_hash:
                    recovered = self._versions.get_snapshot_by_hash(manifest.content_hash)
                if recovered is not None:
                    record.snapshot_id = recovered.snapshot_id
                    record.phase = CommitPhase.SNAPSHOT_CREATED
                    try:
                        self._commits.update(record)
                    except Exception:
                        pass
                else:
                    record.error = str(exc)
                    try:
                        self._commits.update(record)
                    except Exception:
                        pass
                return CommitResult(
                    status=CommitStatus.PENDING_FINALIZE,
                    commit_id=record.commit_id,
                    phase=record.phase,
                    snapshot_id=record.snapshot_id,
                    warnings=["snapshot creation failed; pending_finalize"],
                    detail={"error": str(exc), "recoverable": True},
                )

        if record.phase == CommitPhase.SNAPSHOT_CREATED and record.snapshot_id:
            try:
                version = self._versions.publish_version(record.snapshot_id)
            except Exception as exc:
                existing_version = self._versions.get_version_by_snapshot(record.snapshot_id)
                if existing_version is not None:
                    version = existing_version
                else:
                    record.error = str(exc)
                    self._commits.update(record)
                    return CommitResult(
                        status=CommitStatus.PENDING_FINALIZE,
                        commit_id=record.commit_id,
                        phase=record.phase,
                        warnings=["version publish failed; pending_finalize"],
                        detail={"error": str(exc), "recoverable": True},
                    )

            record.version_id = version.version_id
            record.phase = CommitPhase.PUBLISHED
            record.error = None
            try:
                self._commits.update(record)
            except Exception as exc:
                record.phase = CommitPhase.SNAPSHOT_CREATED
                record.error = f"lifecycle ack failed after publish: {exc}"
                record.version_id = version.version_id
                try:
                    self._commits.update(record)
                except Exception:
                    pass
                return CommitResult(
                    status=CommitStatus.PENDING_FINALIZE,
                    commit_id=record.commit_id,
                    phase=CommitPhase.SNAPSHOT_CREATED,
                    snapshot_id=record.snapshot_id,
                    version_id=version.version_id,
                    warnings=[
                        "version published but lifecycle ack failed; pending_finalize",
                        "retry will reuse the same version idempotently",
                    ],
                    detail={"error": str(exc), "recoverable": True},
                )

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

    def _eligibility(self, report: CurationReport) -> dict[str, Any]:
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
        return {"publishable": True, "reason": "", "warnings": []}

    def _admit_assertions(self, request: CommitRequest) -> list[AdmittedAssertion]:
        decision_by_id = {d.assertion_id: d for d in request.report.decisions}
        admitted: list[AdmittedAssertion] = []
        for assertion in request.assertion_set.assertions:
            decision = decision_by_id.get(assertion.id)
            if decision is None:
                continue
            if decision.action in (CurationAction.REJECT, CurationAction.RETURN_UPSTREAM):
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
            if decision.action == CurationAction.SUPERSEDE:
                admitted.append(
                    AdmittedAssertion(
                        assertion=assertion,
                        visibility=AssertionVisibility.SUPERSEDED,
                        confidence=decision.confidence,
                        action=decision.action,
                    )
                )
                continue
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
            assertion_hash = self._hash_assertion(item.assertion)
            vector_id = (
                f"vec-{request.source.ref_id}-"
                f"{request.source.source_fingerprint[:12]}-"
                f"{item.assertion.id}-"
                f"{assertion_hash[:12]}"
            )
            payloads.append(
                VectorPayload(
                    vector_id=vector_id,
                    ref_id=request.source.ref_id,
                    assertion_id=item.assertion.id,
                    content_hash=assertion_hash,
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
            structural_stage_id=record.commit_id,
            usdo_record_ids=[u.record_id for u in record.usdo_records],
        )
        manifest.content_hash = self._hash_json(manifest.stable_payload())
        return manifest

    def _hash_assertion(self, assertion: Assertion) -> str:
        return self._hash_json(
            {
                "id": assertion.id,
                "ref_id": assertion.ref_id,
                "subject_class": assertion.subject.eddo_class,
                "subject_entity": assertion.subject.resolved_entity,
                "subject_mention": assertion.subject.original_mention,
                "property": assertion.property,
                "value": assertion.object.value,
                "unit": assertion.object.unit,
                "value_type": assertion.object.value_type.value,
                "uncertainty": assertion.object.uncertainty,
                "conditions": [
                    {"c": c.eddo_class, "v": c.value, "u": c.unit} for c in assertion.conditions
                ],
                "locator": assertion.provenance.locator if assertion.provenance else None,
                "sentence": assertion.provenance.sentence if assertion.provenance else None,
                "claim_type": assertion.claim_type.value,
                "origin": assertion.source_claim_origin.value,
                "quality": assertion.quality,
            }
        )

    @staticmethod
    def _hash_json(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_commit_request(request: CommitRequest) -> list[str]:
    """Deterministic CommitRequest binding integrity checks."""
    errors: list[str] = []
    if not request.source.source_fingerprint:
        errors.append("source_fingerprint must be non-empty")
    if request.source.ref_id != request.assertion_set.ref_id:
        errors.append(
            f"source.ref_id ({request.source.ref_id}) != assertion_set.ref_id ({request.assertion_set.ref_id})"
        )
    if request.source.ref_id != request.report.source_ref_id:
        errors.append(
            f"source.ref_id ({request.source.ref_id}) != report.source_ref_id ({request.report.source_ref_id})"
        )

    assertion_ids = [a.id for a in request.assertion_set.assertions]
    if len(assertion_ids) != len(set(assertion_ids)):
        errors.append("duplicate assertion ids in AssertionSet")

    decision_ids = [d.assertion_id for d in request.report.decisions]
    if len(decision_ids) != len(set(decision_ids)):
        errors.append("duplicate decision ids in CurationReport")

    assertion_set_ids = set(assertion_ids)
    decision_set_ids = set(decision_ids)
    missing = assertion_set_ids - decision_set_ids
    extra = decision_set_ids - assertion_set_ids
    if missing:
        errors.append(f"missing decisions for assertions: {sorted(missing)}")
    if extra:
        errors.append(f"decisions referencing unknown assertions: {sorted(extra)}")

    return errors
