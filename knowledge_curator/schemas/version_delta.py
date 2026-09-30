"""Internal temporary version-delta models (Phase 5.2, CG-020).

Not the frozen cross-team public schema. knowledge_curator consumes
upstream-structured content manifests; it does not parse PDF/XML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from knowledge_curator.schemas.assertions import Assertion
from knowledge_curator.schemas.source_versions import VersionRelation


class ContentUnitKind(str, Enum):
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    FORMULA = "formula"
    OTHER = "other"


class DeltaCategory(str, Enum):
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    ADDED = "added"
    REMOVED = "removed"


class DeltaMode(str, Enum):
    DELTA_SAFE = "delta_safe"
    FULL_REEXTRACT_REQUIRED = "full_reextract_required"
    REVIEW_REQUIRED = "review_required"


class TransitionAction(str, Enum):
    SUPERSEDE = "supersede"
    ARCHIVE = "archive"
    ADDED = "added"
    REVIEW_REQUIRED = "review_required"


@dataclass
class ContentUnit:
    """One structured content unit from upstream."""

    unit_id: str
    locator: str
    kind: ContentUnitKind = ContentUnitKind.TEXT
    content_hash: str = ""
    prior_unit_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VersionContentManifest:
    """Structured content manifest for one source version."""

    source_version_id: str
    ref_id: str
    source_fingerprint: str
    units: list[ContentUnit] = field(default_factory=list)
    trace_id: str = ""
    provenance_id: str = ""

    def unit_map(self) -> dict[str, ContentUnit]:
        return {u.unit_id: u for u in self.units}


@dataclass
class AlignedPair:
    prior_unit_id: str
    new_unit_id: str
    category: DeltaCategory


@dataclass
class ContentDeltaPlan:
    """Deterministic cross-version content delta."""

    mode: DeltaMode
    unchanged_pairs: list[AlignedPair] = field(default_factory=list)
    modified_pairs: list[AlignedPair] = field(default_factory=list)
    added_unit_ids: list[str] = field(default_factory=list)
    removed_unit_ids: list[str] = field(default_factory=list)
    extraction_unit_ids: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeltaExtractionRequest:
    """Request for upstream extractor (not the extraction itself)."""

    work_id: str
    prior_source_version_id: str
    new_source_version_id: str
    new_ref_id: str
    extraction_unit_ids: list[str]
    requested_locators: list[str]
    reason: str
    trace_id: str = ""
    provenance_id: str = ""


@dataclass
class VersionAssertionInventory:
    """Assertion inventory bound to content units."""

    source_version_id: str
    ref_id: str
    assertions: list[Assertion] = field(default_factory=list)
    assertion_unit_map: dict[str, str] = field(default_factory=dict)  # assertion_id -> unit_id


@dataclass
class DeltaAssertionBatch:
    """Upstream-extracted assertions for changed/added units only."""

    source_version_id: str
    ref_id: str
    assertions: list[Assertion] = field(default_factory=list)
    assertion_unit_map: dict[str, str] = field(default_factory=dict)
    # CG-020 internal: which units the extractor actually processed.
    # Distinguishes "processed, 0 assertions" from "never processed".
    processed_unit_ids: list[str] = field(default_factory=list)


@dataclass
class CarriedAssertionRecord:
    old_assertion_id: str
    carried_assertion_id: str
    unit_id: str


@dataclass
class AssertionTransition:
    action: TransitionAction
    old_assertion_id: Optional[str] = None
    new_assertion_id: Optional[str] = None
    slot_key: str = ""
    reason: str = ""


@dataclass
class RevisionPackage:
    """Deterministic revision plan (Phase 5.2 output)."""

    package_id: str
    work_id: str
    prior_source_version_id: str
    new_source_version_id: str
    relation: VersionRelation
    prior_ref_id: str
    new_ref_id: str
    prior_bound_kb_version_id: Optional[str]
    content_delta: ContentDeltaPlan
    target_assertions: list[Assertion] = field(default_factory=list)
    supersede_actions: dict[str, str] = field(default_factory=dict)  # old -> new
    archive_actions: list[str] = field(default_factory=list)
    added_assertion_ids: list[str] = field(default_factory=list)
    carried_records: list[CarriedAssertionRecord] = field(default_factory=list)
    transitions: list[AssertionTransition] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    requires_manual_review: bool = False
    lifecycle_reason: str = ""
    trace_id: str = ""
    provenance_id: str = ""
