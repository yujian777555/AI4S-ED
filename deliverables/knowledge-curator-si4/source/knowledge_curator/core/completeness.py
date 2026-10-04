"""Completeness check (docs/03 §5.1). Deterministic rules, no LLM."""

from __future__ import annotations

from knowledge_curator.config import CompletenessConfig, DEFAULT_CONFIG
from knowledge_curator.schemas.assertions import AssertionSet, QualityGrade, ValueType
from knowledge_curator.schemas.curation import (
    CompletenessIssue,
    CompletenessResult,
    CompletenessStatus,
)


def check_completeness(
    assertion_set: AssertionSet,
    config: CompletenessConfig | None = None,
) -> CompletenessResult:
    """Run docs/03 §5.1 completeness checks on one AssertionSet.

    Checks:
      * metadata completeness (title/authors/year/source + DOI or stable_id)
      * non-empty assertions, or explicit "no structured data" declaration
      * numeric assertions must carry units
      * each assertion must have a provenance locator
      * ChartObject quality inputs
      * ParsedDoc quality grade routing (A/B formal, C manual, D/E excluded)

    Args:
        assertion_set: Upstream extraction output (temporary compatibility model).
        config: Optional completeness configuration.

    Returns:
        CompletenessResult with status, issues and routing flags.
    """
    cfg = config or DEFAULT_CONFIG.completeness
    issues: list[CompletenessIssue] = []

    metadata_valid, metadata_issues = _check_metadata(assertion_set, cfg)
    issues.extend(metadata_issues)

    assertions = assertion_set.assertions
    n_assertions = len(assertions)

    explicit_no_data = bool(assertion_set.no_structured_data)
    if n_assertions == 0 and not explicit_no_data:
        issues.append(
            CompletenessIssue(
                code="no_assertions",
                message="no extracted assertions and no explicit no-data declaration",
            )
        )

    missing_unit_ids = [
        a.id
        for a in assertions
        if a.is_numeric
        and (a.missing_unit or a.object.unit is None or str(a.object.unit).strip() == "")
    ]
    if missing_unit_ids:
        issues.append(
            CompletenessIssue(
                code="missing_units",
                message="numeric assertions missing units",
                assertion_ids=missing_unit_ids,
            )
        )

    missing_locator_ids = [a.id for a in assertions if not a.has_locator]
    if missing_locator_ids:
        issues.append(
            CompletenessIssue(
                code="missing_locators",
                message="assertions missing provenance locator",
                assertion_ids=missing_locator_ids,
            )
        )

    chart_issues = _check_charts(assertion_set)
    issues.extend(chart_issues)

    grade = assertion_set.quality_grade
    requires_manual = grade in (QualityGrade.C,)
    excluded = grade in (QualityGrade.D, QualityGrade.E)
    formal_ok = grade in (QualityGrade.A, QualityGrade.B)

    if requires_manual:
        issues.append(
            CompletenessIssue(
                code="parsed_doc_manual_review",
                message=f"ParsedDoc quality_grade={grade.value} requires manual review",
            )
        )
    if excluded:
        issues.append(
            CompletenessIssue(
                code="parsed_doc_not_formal",
                message=f"ParsedDoc quality_grade={grade.value} must not enter formal face",
            )
        )

    status = _derive_status(
        metadata_valid=metadata_valid,
        n_assertions=n_assertions,
        explicit_no_data=explicit_no_data,
        missing_unit_ids=missing_unit_ids,
        missing_locator_ids=missing_locator_ids,
        chart_issues=chart_issues,
        requires_manual=requires_manual,
        excluded=excluded,
        formal_ok=formal_ok,
    )

    requires_return_upstream = status == CompletenessStatus.METADATA_INCOMPLETE
    allows_formal = (
        not excluded
        and not requires_return_upstream
        and not (n_assertions == 0 and not explicit_no_data)
    )

    return CompletenessResult(
        status=status,
        issues=issues,
        metadata_valid=metadata_valid,
        assertion_count=n_assertions,
        allows_formal_curation=allows_formal,
        requires_manual_review=requires_manual or bool(missing_unit_ids),
        requires_return_upstream=requires_return_upstream,
    )


def _check_metadata(
    assertion_set: AssertionSet,
    cfg: CompletenessConfig,
) -> tuple[bool, list[CompletenessIssue]]:
    meta = assertion_set.metadata
    missing: list[str] = []
    for name in cfg.require_metadata_fields:
        value = getattr(meta, name, None)
        if value is None or value == "" or value == []:
            missing.append(name)
    has_id = bool(meta.doi) or bool(meta.stable_id)
    if cfg.require_doi_or_stable_id and not has_id:
        missing.append("doi_or_stable_id")
    if missing:
        return False, [
            CompletenessIssue(
                code="metadata_incomplete",
                message=f"missing metadata fields: {', '.join(missing)}",
            )
        ]
    return True, []


def _check_charts(assertion_set: AssertionSet) -> list[CompletenessIssue]:
    """Validate chart objects without mutating the input ChartObjectInfo."""
    issues: list[CompletenessIssue] = []
    low_ids: list[str] = []
    for chart in assertion_set.charts:
        complete = chart.caption_complete and chart.axes_complete and chart.units_complete
        if chart.not_digitizable or chart.quality_low:
            low_ids.append(chart.id)
            continue
        if not complete:
            low_ids.append(chart.id)
    if low_ids:
        issues.append(
            CompletenessIssue(
                code="chart_quality_low",
                message="chart objects incomplete or marked low quality",
                assertion_ids=low_ids,
            )
        )
    return issues


def _derive_status(
    *,
    metadata_valid: bool,
    n_assertions: int,
    explicit_no_data: bool,
    missing_unit_ids: list[str],
    missing_locator_ids: list[str],
    chart_issues: list[CompletenessIssue],
    requires_manual: bool,
    excluded: bool,
    formal_ok: bool,
) -> CompletenessStatus:
    if not metadata_valid:
        return CompletenessStatus.METADATA_INCOMPLETE
    if excluded:
        return CompletenessStatus.PARSED_DOC_NOT_FORMAL
    if n_assertions == 0 and explicit_no_data:
        return CompletenessStatus.EXPLICIT_NO_DATA
    if n_assertions == 0:
        return CompletenessStatus.NO_ASSERTIONS
    if missing_unit_ids:
        return CompletenessStatus.MISSING_UNITS
    if requires_manual:
        return CompletenessStatus.MANUAL_REVIEW
    if missing_locator_ids:
        return CompletenessStatus.MISSING_LOCATORS
    if chart_issues:
        return CompletenessStatus.CHART_QUALITY_LOW
    if formal_ok:
        return CompletenessStatus.OK
    return CompletenessStatus.MANUAL_REVIEW
