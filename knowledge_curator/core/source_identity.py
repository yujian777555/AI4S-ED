"""Incremental source identity classification (Phase 5.1).

Deterministic intake gate: exact replay / same-work new version / new work /
review-required / identity-conflict. No fuzzy matching, no crawling.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

from knowledge_curator.ports.source_version_registry import SourceVersionRegistry
from knowledge_curator.schemas.source_versions import (
    IntakeDecision,
    IntakeDisposition,
    SourceCandidate,
    SourceKind,
    SourceVersionRecord,
    VersionRelation,
    VersionUpgradeIntent,
    WorkRecord,
)


# ---------------------------------------------------------------------------
# Normalization (safe, deterministic only)
# ---------------------------------------------------------------------------


def normalize_doi(raw: Optional[str]) -> Optional[str]:
    """Safe DOI canonicalization: trim, strip doi:/URL prefixes, casefold.

    Does NOT fuzzy-correct malformed DOI strings.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    s = re.sub(r"^doi:\s*", "", s, flags=re.IGNORECASE)
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :]
            break
    s = s.strip().casefold()
    return s or None


def normalize_title(raw: Optional[str]) -> Optional[str]:
    """Title normalization for exact matching only.

    NFKC + trim + collapse whitespace + casefold. Does NOT strip punctuation.
    """
    if raw is None:
        return None
    s = unicodedata.normalize("NFKC", raw)
    s = " ".join(s.split())
    s = s.casefold()
    return s or None


def normalize_stable_id(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    return s or None


def _hash_json(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# IncrementalIntakeService
# ---------------------------------------------------------------------------


class IncrementalIntakeService:
    """Classify already-discovered source candidates deterministically."""

    def __init__(self, registry: SourceVersionRegistry) -> None:
        self._registry = registry

    # ---- identity helpers ----

    def _source_version_id(self, ref_id: str, fingerprint: str, work_id: str) -> str:
        return _hash_json(
            {"ref_id": ref_id, "fingerprint": fingerprint, "work_id": work_id}
        )[:16]

    def _work_id_new(self, evidence: str) -> str:
        return _hash_json({"new_work": evidence})[:16]

    # ---- classification ----

    def prepare(self, candidate: SourceCandidate) -> IntakeDecision:
        """Classify a source candidate. Does NOT register unless proceed=True."""
        norm_doi = normalize_doi(candidate.doi)
        norm_title = normalize_title(candidate.title)
        norm_stable = normalize_stable_id(candidate.stable_id)
        evidence: list[str] = []
        diagnostics: dict[str, Any] = {
            "normalized_doi": norm_doi,
            "normalized_title": norm_title,
            "stable_id": norm_stable,
        }

        # A. exact replay: same ref_id + source_fingerprint
        existing = self._registry.lookup_by_ref_fingerprint(
            candidate.ref_id, candidate.source_fingerprint
        )
        if existing is not None:
            # R2-A: validate supplied explicit lineage against existing record.
            lineage_conflict = self._replay_lineage_conflict(existing, candidate)
            if lineage_conflict is not None:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    work_id=existing.work_id,
                    existing_source_version_id=existing.source_version_id,
                    match_evidence=["exact_ref_fingerprint", "explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": lineage_conflict,
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            if self._replay_material_conflict(existing, candidate, norm_doi, norm_title, norm_stable):
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    work_id=existing.work_id,
                    existing_source_version_id=existing.source_version_id,
                    match_evidence=["exact_ref_fingerprint"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": "material metadata contradiction on replay",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            evidence.append("exact_ref_fingerprint")
            return IntakeDecision(
                disposition=IntakeDisposition.EXACT_REPLAY,
                work_id=existing.work_id,
                existing_source_version_id=existing.source_version_id,
                match_evidence=evidence,
                diagnostics=diagnostics,
                proceed_to_commit=False,
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # Gather identifier mappings
        doi_hits = self._registry.lookup_by_doi(norm_doi) if norm_doi else []
        stable_hits = self._registry.lookup_by_stable_id(norm_stable) if norm_stable else []
        title_hits = (
            self._registry.lookup_by_normalized_title(norm_title) if norm_title else []
        )

        doi_works = {r.work_id for r in doi_hits}
        stable_works = {r.work_id for r in stable_hits}
        title_works = {r.work_id for r in title_hits}

        # --- Cross-identifier invariants BEFORE any positive return (R1) ---

        # DOI mapped to multiple works
        if len(doi_works) > 1:
            return IntakeDecision(
                disposition=IntakeDisposition.IDENTITY_CONFLICT,
                match_evidence=["exact_doi"],
                ambiguity_candidates=sorted(doi_works),
                diagnostics={**diagnostics, "conflict_reason": "DOI maps to multiple works"},
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # stable_id mapped to multiple works
        if len(stable_works) > 1:
            return IntakeDecision(
                disposition=IntakeDisposition.IDENTITY_CONFLICT,
                match_evidence=["exact_stable_id"],
                ambiguity_candidates=sorted(stable_works),
                diagnostics={**diagnostics, "conflict_reason": "stable_id maps to multiple works"},
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # DOI and stable_id disagree on work identity
        if len(doi_works) == 1 and len(stable_works) == 1 and doi_works != stable_works:
            return IntakeDecision(
                disposition=IntakeDisposition.IDENTITY_CONFLICT,
                match_evidence=["exact_doi", "exact_stable_id"],
                ambiguity_candidates=sorted(doi_works | stable_works),
                diagnostics={**diagnostics, "conflict_reason": "DOI/stable_id work mismatch"},
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # B. explicit lineage — enter when work_id, prior_version_id, or non-NONE relation
        has_explicit_lineage = (
            candidate.explicit_work_id is not None
            or candidate.explicit_prior_version_id is not None
            or (
                candidate.explicit_relation is not None
                and candidate.explicit_relation != VersionRelation.NONE
            )
        )
        if has_explicit_lineage:
            decision = self._classify_explicit_lineage(
                candidate,
                norm_doi=norm_doi,
                norm_title=norm_title,
                norm_stable=norm_stable,
                doi_works=doi_works,
                stable_works=stable_works,
                evidence=evidence,
                diagnostics=diagnostics,
            )
            if decision is not None:
                return decision

        # C. exact DOI (only after invariant checks passed)
        if norm_doi and len(doi_works) == 1:
            work_id = next(iter(doi_works))
            evidence.append("exact_doi")
            diagnostics["title_changed"] = bool(
                title_hits and norm_title
                and all(r.normalized_title != norm_title for r in doi_hits)
            )
            return IntakeDecision(
                disposition=IntakeDisposition.SAME_WORK_NEW_VERSION,
                work_id=work_id,
                match_evidence=evidence,
                diagnostics=diagnostics,
                proceed_to_commit=True,
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # D. exact stable_id
        if norm_stable and len(stable_works) == 1:
            work_id = next(iter(stable_works))
            evidence.append("exact_stable_id")
            return IntakeDecision(
                disposition=IntakeDisposition.SAME_WORK_NEW_VERSION,
                work_id=work_id,
                match_evidence=evidence,
                diagnostics=diagnostics,
                proceed_to_commit=True,
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # E. title-only -> REVIEW_REQUIRED (no auto-merge)
        if norm_title and title_works:
            evidence.append("exact_title_review_only")
            return IntakeDecision(
                disposition=IntakeDisposition.REVIEW_REQUIRED,
                match_evidence=evidence,
                ambiguity_candidates=sorted(title_works),
                diagnostics={**diagnostics, "note": "title-only match is not sufficient"},
                proceed_to_commit=False,
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # F. no match
        evidence.append("no_match")
        return IntakeDecision(
            disposition=IntakeDisposition.NEW_WORK,
            match_evidence=evidence,
            diagnostics=diagnostics,
            proceed_to_commit=True,
            trace_id=candidate.trace_id,
            provenance_id=candidate.provenance_id,
        )

    def _replay_lineage_conflict(
        self,
        existing: SourceVersionRecord,
        candidate: SourceCandidate,
    ) -> Optional[str]:
        """R2-A: return conflict reason if explicit lineage contradicts existing record."""
        # explicit_work_id must match existing work
        if candidate.explicit_work_id is not None:
            work = self._registry.get_work(candidate.explicit_work_id)
            if work is None:
                return "explicit_work_id not found on replay"
            if candidate.explicit_work_id != existing.work_id:
                return (
                    f"explicit_work_id {candidate.explicit_work_id} contradicts "
                    f"existing work {existing.work_id}"
                )

        # explicit_prior must belong to existing work
        if candidate.explicit_prior_version_id is not None:
            prior = self._registry.get_source_version(candidate.explicit_prior_version_id)
            if prior is None:
                return "explicit_prior_version_id not found on replay"
            if prior.work_id != existing.work_id:
                return (
                    f"explicit prior work {prior.work_id} contradicts "
                    f"existing work {existing.work_id}"
                )

        # explicit_relation must not contradict existing material
        rel = candidate.explicit_relation
        if rel is not None and rel != VersionRelation.NONE:
            if rel == VersionRelation.PREPRINT_TO_JOURNAL:
                if existing.source_kind != SourceKind.PREPRINT:
                    return (
                        f"PREPRINT_TO_JOURNAL replay but existing source_kind "
                        f"is {existing.source_kind.value}"
                    )
                if candidate.source_kind != SourceKind.JOURNAL:
                    return (
                        f"PREPRINT_TO_JOURNAL replay but candidate source_kind "
                        f"is {candidate.source_kind.value}"
                    )
            # REVISION_OF / CORRECTED_VERSION / EXPLICIT_SAME_WORK on replay:
            # prior must be in same work (already checked above if supplied).
            # No additional contradiction for a true replay.
        elif rel is VersionRelation.NONE and (
            candidate.explicit_work_id is not None
            or candidate.explicit_prior_version_id is not None
        ):
            return "explicit_relation=NONE contradicts supplied explicit lineage"
        return None

    def _replay_material_conflict(
        self,
        existing: SourceVersionRecord,
        candidate: SourceCandidate,
        norm_doi: Optional[str],
        norm_title: Optional[str],
        norm_stable: Optional[str],
    ) -> bool:
        """Same ref+fingerprint with contradictory identity metadata -> conflict."""
        if norm_doi is not None and existing.normalized_doi is not None:
            if norm_doi != existing.normalized_doi:
                return True
        if norm_stable is not None and existing.stable_id is not None:
            if norm_stable != existing.stable_id:
                return True
        if norm_title is not None and existing.normalized_title is not None:
            # Title change alone is diagnostic, not identity conflict for replay
            # unless DOI also conflicts. Only treat as conflict when title is the
            # sole identity evidence and it changed.
            if (
                existing.normalized_doi is None
                and existing.stable_id is None
                and norm_title != existing.normalized_title
            ):
                return True
        return False

    def _classify_explicit_lineage(
        self,
        candidate: SourceCandidate,
        *,
        norm_doi: Optional[str],
        norm_title: Optional[str],
        norm_stable: Optional[str],
        doi_works: set[str],
        stable_works: set[str],
        evidence: list[str],
        diagnostics: dict[str, Any],
    ) -> Optional[IntakeDecision]:
        """Handle explicit_work_id / explicit_prior_version_id / explicit_relation."""
        work_id = candidate.explicit_work_id
        prior_id = candidate.explicit_prior_version_id
        rel = candidate.explicit_relation  # None = omitted; NONE = explicitly set
        prior = None

        # R2-B: explicit NONE + explicit lineage fields => conflict
        if rel is VersionRelation.NONE and (work_id is not None or prior_id is not None):
            return IntakeDecision(
                disposition=IntakeDisposition.IDENTITY_CONFLICT,
                match_evidence=["explicit_lineage"],
                diagnostics={
                    **diagnostics,
                    "conflict_reason": "explicit_relation=NONE contradicts supplied explicit lineage",
                },
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # Relation-only requests (non-NONE relation, no work/prior)
        if rel is not None and rel != VersionRelation.NONE:
            if work_id is None and prior_id is None:
                # EXPLICIT_SAME_WORK requires at least work or prior
                # P2J / REVISION_OF / CORRECTED_VERSION require prior
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": f"relation {rel.value} requires explicit lineage target",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )

        # Validate explicit_work_id existence
        if work_id is not None:
            work = self._registry.get_work(work_id)
            if work is None:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={**diagnostics, "conflict_reason": "explicit_work_id not found"},
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )

        # Validate prior
        if prior_id is not None:
            prior = self._registry.get_source_version(prior_id)
            if prior is None:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": "explicit_prior_version_id not found",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            if work_id is not None and prior.work_id != work_id:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": "explicit prior does not belong to explicit work",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            # Prior-only: inherit work from prior
            work_id = work_id or prior.work_id

        if work_id is None:
            # No work resolved (should not happen when has_explicit_lineage)
            return IntakeDecision(
                disposition=IntakeDisposition.IDENTITY_CONFLICT,
                match_evidence=["explicit_lineage"],
                diagnostics={
                    **diagnostics,
                    "conflict_reason": "explicit lineage could not resolve work",
                },
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # DOI/stable disagreement vs resolved work
        if doi_works and work_id not in doi_works:
            return IntakeDecision(
                disposition=IntakeDisposition.IDENTITY_CONFLICT,
                match_evidence=["explicit_lineage", "exact_doi"],
                ambiguity_candidates=sorted(doi_works | {work_id}),
                diagnostics={
                    **diagnostics,
                    "conflict_reason": "DOI maps to Work A but explicit lineage resolves Work B",
                },
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )
        if stable_works and work_id not in stable_works:
            return IntakeDecision(
                disposition=IntakeDisposition.IDENTITY_CONFLICT,
                match_evidence=["explicit_lineage", "exact_stable_id"],
                ambiguity_candidates=sorted(stable_works | {work_id}),
                diagnostics={
                    **diagnostics,
                    "conflict_reason": "stable_id maps to different work than explicit lineage",
                },
                trace_id=candidate.trace_id,
                provenance_id=candidate.provenance_id,
            )

        # Relation state machine
        if rel is None:
            # Omitted relation: deterministic defaults
            relation = (
                VersionRelation.REVISION_OF
                if prior_id is not None
                else VersionRelation.EXPLICIT_SAME_WORK
            )
        else:
            relation = rel

        # Enforce relation requirements
        if relation == VersionRelation.PREPRINT_TO_JOURNAL:
            if prior_id is None or prior is None:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": "PREPRINT_TO_JOURNAL requires explicit_prior_version_id",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            if prior.work_id != work_id:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": "PREPRINT_TO_JOURNAL prior does not belong to resolved work",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            if prior.source_kind != SourceKind.PREPRINT:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": f"PREPRINT_TO_JOURNAL prior source_kind is {prior.source_kind.value}, expected preprint",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            if candidate.source_kind != SourceKind.JOURNAL:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": f"PREPRINT_TO_JOURNAL candidate source_kind is {candidate.source_kind.value}, expected journal",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
        elif relation in (VersionRelation.REVISION_OF, VersionRelation.CORRECTED_VERSION):
            if prior_id is None or prior is None:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": f"{relation.value} requires explicit_prior_version_id",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            if prior.work_id != work_id:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": f"{relation.value} prior does not belong to resolved work",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
        elif relation == VersionRelation.EXPLICIT_SAME_WORK:
            if work_id is None and prior_id is None:
                return IntakeDecision(
                    disposition=IntakeDisposition.IDENTITY_CONFLICT,
                    match_evidence=["explicit_lineage"],
                    diagnostics={
                        **diagnostics,
                        "conflict_reason": "EXPLICIT_SAME_WORK requires work or prior",
                    },
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )

        evidence.append("explicit_lineage")
        diagnostics["explicit_relation"] = relation.value

        # Build upgrade intent for PREPRINT_TO_JOURNAL (Phase 5.2 input)
        upgrade_intent = None
        if relation == VersionRelation.PREPRINT_TO_JOURNAL and prior_id:
            new_vid = self._source_version_id(
                candidate.ref_id, candidate.source_fingerprint, work_id
            )
            upgrade_intent = VersionUpgradeIntent(
                work_id=work_id,
                prior_source_version_id=prior_id,
                new_source_version_id=new_vid,
                relation=relation,
                base_kb_version_id=prior.kb_version_id if prior else None,
                requires_delta_extraction=True,
                lifecycle_reason="preprint_to_journal",
            )

        return IntakeDecision(
            disposition=IntakeDisposition.SAME_WORK_NEW_VERSION,
            work_id=work_id,
            match_evidence=evidence,
            diagnostics=diagnostics,
            proceed_to_commit=True,
            upgrade_intent=upgrade_intent,
            trace_id=candidate.trace_id,
            provenance_id=candidate.provenance_id,
        )

    # ---- registration ----

    def proceed(
        self,
        candidate: SourceCandidate,
        decision: IntakeDecision,
    ) -> SourceVersionRecord:
        """Register a prepared source version for NEW_WORK / SAME_WORK_NEW_VERSION."""
        if decision.disposition not in (
            IntakeDisposition.NEW_WORK,
            IntakeDisposition.SAME_WORK_NEW_VERSION,
        ):
            raise ValueError(
                f"cannot register source version for disposition {decision.disposition}"
            )
        if not decision.proceed_to_commit:
            raise ValueError("decision does not permit registration")

        norm_doi = normalize_doi(candidate.doi)
        norm_title = normalize_title(candidate.title)
        norm_stable = normalize_stable_id(candidate.stable_id)

        if decision.disposition == IntakeDisposition.NEW_WORK:
            work_id = self._work_id_new(
                f"{candidate.ref_id}:{candidate.source_fingerprint}"
            )
            self._registry.append_work(
                WorkRecord(
                    work_id=work_id,
                    created_evidence="new_work",
                    trace_id=candidate.trace_id,
                    provenance_id=candidate.provenance_id,
                )
            )
        else:
            work_id = decision.work_id
            if work_id is None:
                raise ValueError("SAME_WORK_NEW_VERSION requires work_id")
            if self._registry.get_work(work_id) is None:
                self._registry.append_work(
                    WorkRecord(
                        work_id=work_id,
                        created_evidence="explicit_or_identifier",
                        trace_id=candidate.trace_id,
                        provenance_id=candidate.provenance_id,
                    )
                )

        relation = candidate.explicit_relation or (
            VersionRelation.REVISION_OF
            if decision.disposition == IntakeDisposition.SAME_WORK_NEW_VERSION
            else VersionRelation.NONE
        )
        vid = self._source_version_id(
            candidate.ref_id, candidate.source_fingerprint, work_id
        )
        record = SourceVersionRecord(
            source_version_id=vid,
            work_id=work_id,
            ref_id=candidate.ref_id,
            source_fingerprint=candidate.source_fingerprint,
            normalized_doi=norm_doi,
            normalized_title=norm_title,
            stable_id=norm_stable,
            source_kind=candidate.source_kind,
            relation=relation,
            prior_source_version_id=candidate.explicit_prior_version_id,
            raw_title=candidate.title,
            raw_doi=candidate.doi,
            trace_id=candidate.trace_id,
            provenance_id=candidate.provenance_id,
        )
        stored = self._registry.append_source_version(record)
        decision.prepared_source_version_id = stored.source_version_id
        decision.work_id = work_id
        return stored

    # ---- bind after KB publish ----

    def finalize_bind(
        self,
        source_version_id: str,
        *,
        kb_version_id: str,
        snapshot_id: str,
        commit_status: str,
    ) -> SourceVersionRecord:
        """Bind source version to a published KB version. Fail closed otherwise."""
        allowed = {"published", "idempotent_hit"}
        if commit_status not in allowed:
            raise ValueError(
                f"cannot bind source version on commit_status={commit_status}"
            )
        return self._registry.bind_source_version(
            source_version_id, kb_version_id, snapshot_id
        )
