"""KnowledgeCurator main service (runtime-independent, 03 §5 core).

Pipeline order is fixed:
    completeness -> conflict detection -> quality evaluation
        -> curation decision -> CurationReport

Core must stay independent of DSH / SQLite / FAISS / HTTP.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from knowledge_curator.config import CuratorConfig, DEFAULT_CONFIG
from knowledge_curator.core.completeness import check_completeness
from knowledge_curator.core.conflict import detect_conflicts
from knowledge_curator.core.decision import decide_assertion
from knowledge_curator.core.quality import evaluate_quality
from knowledge_curator.ports.knowledge_repository import KnowledgeRepository
from knowledge_curator.ports.mechanism_validator import MechanismValidator
from knowledge_curator.ports.ontology_service import OntologyService
from knowledge_curator.schemas.assertions import Assertion, AssertionSet
from knowledge_curator.schemas.curation import (
    AssertionDecision,
    ConflictType,
    CurationAction,
    CurationReport,
)


class KnowledgeCurator:
    """Phase 1 curator: AssertionSet -> CurationReport.

    Args:
        repository: Port for existing graph assertions (find/commit).
        ontology: Port for entity/condition normalization queries.
        mechanism_validator: Optional L3 mechanism validator port.
        config: Centralized rule configuration.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        ontology: OntologyService,
        mechanism_validator: Optional[MechanismValidator] = None,
        config: Optional[CuratorConfig] = None,
    ) -> None:
        self._repository = repository
        self._ontology = ontology
        self._mechanism = mechanism_validator
        self._config = config or DEFAULT_CONFIG

    async def curate(
        self,
        assertion_set: AssertionSet,
        context: Optional[dict[str, Any]] = None,
    ) -> CurationReport:
        """Run the full §5 curation pipeline on one AssertionSet.

        Args:
            assertion_set: Upstream extraction package (temporary model).
            context: Optional extra context reserved for Phase 2+ adapters.

        Returns:
            CurationReport with completeness, conflicts, decisions and quality.
        """
        ctx = dict(context or {})
        report_id = ctx.get("report_id") or f"cr-{uuid.uuid4().hex[:12]}"

        # 1) Completeness (§5.1)
        completeness = check_completeness(assertion_set, self._config.completeness)

        # 2) Conflict detection (§5.2)
        conflicts = detect_conflicts(
            assertion_set.assertions,
            repository=self._repository,
            ontology=self._ontology,
            mechanism_validator=self._mechanism,
            config=self._config.conflict,
            run_mechanism_check=self._config.enable_mechanism_check,
        )

        # 3) Quality evaluation (§5.3)
        quality = evaluate_quality(
            assertion_set,
            completeness,
            conflicts,
            self._config.quality,
        )

        # 4) Per-assertion curation decisions
        decisions: list[AssertionDecision] = []
        for assertion in assertion_set.assertions:
            related = [
                f
                for f in conflicts
                if f.new_assertion_id == assertion.id
                or f.existing_assertion_id == assertion.id
            ]
            decision = decide_assertion(
                assertion,
                completeness,
                related,
                quality,
                self._config,
            )
            decisions.append(decision)

        counts = _count_actions(decisions)
        status = _derive_report_status(completeness.status.value, counts, decisions)

        warnings = [issue.message for issue in completeness.issues]
        for d in decisions:
            warnings.extend(d.warnings)
        if quality.total < self._config.quality.low_quality_threshold:
            warnings.append(
                f"document quality {quality.total:.3f} below threshold "
                f"{self._config.quality.low_quality_threshold}"
            )

        return CurationReport(
            report_id=report_id,
            source_ref_id=assertion_set.ref_id,
            status=status,
            completeness=completeness,
            conflicts=conflicts,
            decisions=decisions,
            quality=quality,
            accepted_count=counts.get(CurationAction.ACCEPT, 0),
            downgraded_count=counts.get(CurationAction.DOWNGRADE, 0),
            rejected_count=counts.get(CurationAction.REJECT, 0),
            pending_count=counts.get(CurationAction.PENDING_REVIEW, 0),
            superseded_count=counts.get(CurationAction.SUPERSEDE, 0),
            returned_upstream_count=counts.get(CurationAction.RETURN_UPSTREAM, 0),
            warnings=warnings,
            trace={
                "pipeline": [
                    "completeness",
                    "conflict_detection",
                    "quality_evaluation",
                    "curation_decision",
                ],
                "context_keys": sorted(ctx.keys()),
                "assertion_ids": [a.id for a in assertion_set.assertions],
            },
            # commit_id / kb_version / snapshot_id intentionally left None in Phase 1
        )


def _count_actions(decisions: list[AssertionDecision]) -> dict[CurationAction, int]:
    counts: dict[CurationAction, int] = {}
    for d in decisions:
        counts[d.action] = counts.get(d.action, 0) + 1
    return counts


def _derive_report_status(
    completeness_status: str,
    counts: dict[CurationAction, int],
    decisions: list[AssertionDecision],
) -> str:
    if counts.get(CurationAction.RETURN_UPSTREAM, 0) > 0:
        return "return_upstream"
    if not decisions:
        return "no_assertions"
    if counts.get(CurationAction.ACCEPT, 0) == len(decisions):
        return "successful"
    if counts.get(CurationAction.REJECT, 0) == len(decisions):
        return "rejected"
    if counts.get(CurationAction.PENDING_REVIEW, 0) > 0:
        return "pending_review"
    if counts.get(CurationAction.DOWNGRADE, 0) > 0:
        return "downgraded"
    return "partial"
