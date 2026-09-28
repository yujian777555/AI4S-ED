"""JSON codec for temporary compatibility AssertionSet / CurationReport.

Translates JSON <-> existing dataclasses/enums without redefining semantics.
Rejects malformed input and unknown enum values cleanly.
"""

from __future__ import annotations

from typing import Any

from knowledge_curator.schemas.assertions import (
    Assertion,
    AssertionSet,
    ChartObjectInfo,
    ClaimType,
    Condition,
    Confidence,
    DocumentMetadata,
    ObjectValue,
    Provenance,
    QualityGrade,
    SourceClaimOrigin,
    Subject,
    ValueType,
)
from knowledge_curator.schemas.curation import (
    AssertionDecision,
    CompletenessIssue,
    CompletenessResult,
    CompletenessStatus,
    ConflictFinding,
    ConflictType,
    CurationAction,
    CurationReport,
    QualityBreakdown,
)


class CodecError(ValueError):
    """Raised for malformed payloads or invalid enum values."""


def _require_dict(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise CodecError(f"{label} must be an object")
    return value


def _require_str(data: dict, key: str, label: str) -> str:
    if key not in data or data[key] is None:
        raise CodecError(f"{label}.{key} is required")
    if not isinstance(data[key], str):
        raise CodecError(f"{label}.{key} must be a string")
    return data[key]


def _enum(enum_cls, value: Any, label: str):
    try:
        return enum_cls(value)
    except Exception as exc:
        allowed = ", ".join(e.value for e in enum_cls)
        raise CodecError(f"{label} invalid: {value!r}; allowed: {allowed}") from exc


def parse_assertion_set(payload: dict[str, Any]) -> AssertionSet:
    """Parse AssertionSet JSON into the temporary compatibility dataclass."""
    data = _require_dict(payload, "assertion_set")
    ref_id = _require_str(data, "ref_id", "assertion_set")

    meta_raw = _require_dict(data.get("metadata"), "assertion_set.metadata")
    metadata = DocumentMetadata(
        title=str(meta_raw.get("title") or ""),
        authors=list(meta_raw.get("authors") or []),
        year=meta_raw.get("year"),
        source=str(meta_raw.get("source") or ""),
        doi=meta_raw.get("doi"),
        stable_id=meta_raw.get("stable_id"),
    )

    assertions_raw = data.get("assertions")
    if assertions_raw is None:
        raise CodecError("assertion_set.assertions is required")
    if not isinstance(assertions_raw, list):
        raise CodecError("assertion_set.assertions must be an array")

    assertions = [parse_assertion(item, i) for i, item in enumerate(assertions_raw)]

    grade_raw = data.get("quality_grade", "B")
    grade = _enum(QualityGrade, grade_raw, "assertion_set.quality_grade")

    charts = []
    for i, c in enumerate(data.get("charts") or []):
        cd = _require_dict(c, f"charts[{i}]")
        charts.append(
            ChartObjectInfo(
                id=_require_str(cd, "id", f"charts[{i}]"),
                caption_complete=bool(cd.get("caption_complete", True)),
                axes_complete=bool(cd.get("axes_complete", True)),
                units_complete=bool(cd.get("units_complete", True)),
                not_digitizable=bool(cd.get("not_digitizable", False)),
                quality_low=bool(cd.get("quality_low", False)),
            )
        )

    return AssertionSet(
        ref_id=ref_id,
        metadata=metadata,
        assertions=assertions,
        quality_grade=grade,
        charts=charts,
        no_structured_data=bool(data.get("no_structured_data", False)),
        schema_valid_count=data.get("schema_valid_count"),
        schema_total_count=data.get("schema_total_count"),
    )


def parse_assertion(item: Any, index: int) -> Assertion:
    data = _require_dict(item, f"assertions[{index}]")
    label = f"assertions[{index}]"
    aid = _require_str(data, "id", label)
    ref_id = _require_str(data, "ref_id", label)

    subject_raw = _require_dict(data.get("subject"), f"{label}.subject")
    subject = Subject(
        eddo_class=_require_str(subject_raw, "eddo_class", f"{label}.subject"),
        resolved_entity=_require_str(subject_raw, "resolved_entity", f"{label}.subject"),
        original_mention=str(subject_raw.get("original_mention") or ""),
    )

    property_name = _require_str(data, "property", label)

    obj_raw = _require_dict(data.get("object"), f"{label}.object")
    if "value" not in obj_raw:
        raise CodecError(f"{label}.object.value is required")
    value_type = _enum(ValueType, obj_raw.get("value_type", "number"), f"{label}.object.value_type")
    obj = ObjectValue(
        value=obj_raw["value"],
        unit=obj_raw.get("unit"),
        value_type=value_type,
        uncertainty=obj_raw.get("uncertainty"),
    )

    conditions = []
    for j, c in enumerate(data.get("conditions") or []):
        cd = _require_dict(c, f"{label}.conditions[{j}]")
        conditions.append(
            Condition(
                eddo_class=_require_str(cd, "eddo_class", f"{label}.conditions[{j}]"),
                value=cd.get("value"),
                unit=cd.get("unit"),
            )
        )

    provenance = None
    if data.get("provenance") is not None:
        pd = _require_dict(data["provenance"], f"{label}.provenance")
        locator = pd.get("locator")
        if locator is None:
            # Missing locator is a completeness signal — keep None so gate sees it.
            provenance = None
        else:
            provenance = Provenance(
                locator=str(locator),
                sentence=pd.get("sentence"),
            )

    claim_type = _enum(ClaimType, data.get("claim_type", "measurement"), f"{label}.claim_type")
    origin = _enum(
        SourceClaimOrigin,
        data.get("source_claim_origin", "primary"),
        f"{label}.source_claim_origin",
    )
    confidence = _enum(Confidence, data.get("confidence", "medium"), f"{label}.confidence")

    quality = data.get("quality", 0.5)
    try:
        quality = float(quality)
    except Exception as exc:
        raise CodecError(f"{label}.quality must be a number") from exc

    return Assertion(
        id=aid,
        ref_id=ref_id,
        subject=subject,
        property=property_name,
        object=obj,
        conditions=conditions,
        provenance=provenance,
        claim_type=claim_type,
        source_claim_origin=origin,
        confidence=confidence,
        quality=quality,
        missing_unit=bool(data.get("missing_unit", False)),
        speculative_wording=bool(data.get("speculative_wording", False)),
        chart_quality_low=bool(data.get("chart_quality_low", False)),
    )


def serialize_curation_report(report: CurationReport) -> dict[str, Any]:
    """Deterministic JSON-friendly serialization of a CurationReport."""
    completeness = report.completeness
    quality = report.quality
    return {
        "report_id": report.report_id,
        "source_ref_id": report.source_ref_id,
        "status": report.status,
        "completeness": {
            "status": completeness.status.value,
            "metadata_valid": completeness.metadata_valid,
            "assertion_count": completeness.assertion_count,
            "allows_formal_curation": completeness.allows_formal_curation,
            "requires_manual_review": completeness.requires_manual_review,
            "requires_return_upstream": completeness.requires_return_upstream,
            "issues": [
                {
                    "code": i.code,
                    "message": i.message,
                    "assertion_ids": list(i.assertion_ids),
                }
                for i in completeness.issues
            ],
        },
        "conflicts": [
            {
                "conflict_type": f.conflict_type.value,
                "new_assertion_id": f.new_assertion_id,
                "existing_assertion_id": f.existing_assertion_id,
                "message": f.message,
                "detail": f.detail,
            }
            for f in report.conflicts
        ],
        "decisions": [
            {
                "assertion_id": d.assertion_id,
                "action": d.action.value,
                "confidence": d.confidence.value,
                "reason": d.reason,
                "conflict_type": d.conflict_type.value,
                "warnings": list(d.warnings),
            }
            for d in report.decisions
        ],
        "quality": None
        if quality is None
        else {
            "p_parse": quality.p_parse,
            "s_schema": quality.s_schema,
            "e_evidence": quality.e_evidence,
            "n_novelty": quality.n_novelty,
            "penalty": quality.penalty,
            "total": quality.total,
        },
        "counts": {
            "accepted": report.accepted_count,
            "downgraded": report.downgraded_count,
            "rejected": report.rejected_count,
            "pending": report.pending_count,
            "superseded": report.superseded_count,
            "returned_upstream": report.returned_upstream_count,
        },
        "warnings": list(report.warnings),
        "trace": report.trace,
        "commit_id": report.commit_id,
        "kb_version": report.kb_version,
        "snapshot_id": report.snapshot_id,
    }
