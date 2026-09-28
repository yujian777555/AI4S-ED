"""Completeness check tests (docs/03 §5.1)."""

from __future__ import annotations

from knowledge_curator.core.completeness import check_completeness
from knowledge_curator.schemas.assertions import QualityGrade
from knowledge_curator.schemas.curation import CompletenessStatus
from knowledge_curator.tests.conftest import make_assertion, make_assertion_set, make_meta


def test_t02_no_doi_but_stable_id_is_valid_metadata():
    """T02: no DOI but stable_id present -> metadata valid."""
    aset = make_assertion_set(
        metadata=make_meta(doi=None, stable_id="STABLE-42"),
    )
    result = check_completeness(aset)
    assert result.metadata_valid is True
    assert result.status == CompletenessStatus.OK
    assert result.requires_return_upstream is False


def test_t03_missing_doi_and_stable_id_requires_return_upstream():
    """T03: DOI and stable_id both missing -> incomplete / return_upstream."""
    aset = make_assertion_set(
        metadata=make_meta(doi=None, stable_id=None),
    )
    result = check_completeness(aset)
    assert result.metadata_valid is False
    assert result.status == CompletenessStatus.METADATA_INCOMPLETE
    assert result.requires_return_upstream is True


def test_t04_numeric_missing_unit_flagged():
    """T04: numeric assertion missing unit -> completeness issue."""
    a = make_assertion("AS-U1", unit=None, missing_unit=True)
    aset = make_assertion_set([a])
    result = check_completeness(aset)
    assert result.status == CompletenessStatus.MISSING_UNITS
    assert any(i.code == "missing_units" for i in result.issues)
    assert "AS-U1" in result.issues[0].assertion_ids or any(
        "AS-U1" in i.assertion_ids for i in result.issues
    )


def test_t05_missing_locator_flagged():
    """T05: locator missing -> completeness issue for that assertion."""
    a = make_assertion("AS-L1", locator=None)
    aset = make_assertion_set([a])
    result = check_completeness(aset)
    assert result.status == CompletenessStatus.MISSING_LOCATORS
    assert any(i.code == "missing_locators" and "AS-L1" in i.assertion_ids for i in result.issues)


def test_no_assertions_without_explicit_no_data():
    aset = make_assertion_set([], no_structured_data=False)
    result = check_completeness(aset)
    assert result.status == CompletenessStatus.NO_ASSERTIONS
    assert result.allows_formal_curation is False


def test_explicit_no_structured_data_allowed():
    aset = make_assertion_set([], no_structured_data=True)
    result = check_completeness(aset)
    assert result.status == CompletenessStatus.EXPLICIT_NO_DATA
    assert result.requires_return_upstream is False


def test_grade_c_requires_manual_review():
    aset = make_assertion_set(quality_grade=QualityGrade.C)
    result = check_completeness(aset)
    assert result.requires_manual_review is True
    assert result.status == CompletenessStatus.MANUAL_REVIEW


def test_grade_d_excluded_from_formal_face():
    aset = make_assertion_set(quality_grade=QualityGrade.D)
    result = check_completeness(aset)
    assert result.status == CompletenessStatus.PARSED_DOC_NOT_FORMAL
    assert result.allows_formal_curation is False


def test_chart_quality_low_when_incomplete():
    from knowledge_curator.schemas.assertions import ChartObjectInfo

    charts = [ChartObjectInfo(id="C1", caption_complete=False)]
    aset = make_assertion_set(charts=charts)
    result = check_completeness(aset)
    assert result.status == CompletenessStatus.CHART_QUALITY_LOW
    assert any(i.code == "chart_quality_low" for i in result.issues)


def test_t01_normal_assertion_set_completeness_ok():
    """T01 completeness stage: normal package is OK."""
    aset = make_assertion_set()
    result = check_completeness(aset)
    assert result.status == CompletenessStatus.OK
    assert result.allows_formal_curation is True
    assert result.requires_return_upstream is False
