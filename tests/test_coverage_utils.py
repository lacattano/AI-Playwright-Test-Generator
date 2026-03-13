"""Unit tests for coverage utilities."""

from __future__ import annotations

from src.coverage_utils import (
    RequirementCoverage,
    build_coverage_analysis,
    build_requirement_coverages,
    extract_test_names,
)


def test_extract_test_names_returns_empty_for_no_code() -> None:
    """extract_test_names should handle empty input gracefully."""
    assert extract_test_names("") == []
    assert extract_test_names("print('no tests here')") == []


def test_extract_test_names_finds_pytest_functions() -> None:
    """extract_test_names finds top-level pytest-style test functions."""
    code = """
def helper():
    pass

def test_01_login(page):
    pass

def test_something_else():
    pass
"""
    names = extract_test_names(code)
    assert "test_01_login" in names
    assert "test_something_else" in names
    assert "helper" not in names


def test_build_requirement_coverages_uses_numbered_matching() -> None:
    """Requirements should link to tests by numbered suffix when available."""
    criteria = ["First thing", "Second thing"]
    code = """
def test_01_first_thing(page):
    pass

def test_2_second_thing(page):
    pass
"""
    requirements: list[RequirementCoverage] = build_requirement_coverages(criteria, code)

    assert len(requirements) == 2
    assert requirements[0].id == "TC-001"
    assert requirements[0].status == "covered"
    assert any("test_01_first_thing" == name for name in requirements[0].linked_tests)

    assert requirements[1].id == "TC-002"
    assert requirements[1].status == "covered"
    assert any("test_2_second_thing" == name for name in requirements[1].linked_tests)


def test_build_requirement_coverages_uses_word_overlap_fallback() -> None:
    """When numbering does not match, fall back to shared words."""
    criteria = ["User can reset password via email"]
    code = """
def test_reset_password_email_flow(page):
    pass
"""
    requirements = build_requirement_coverages(criteria, code)
    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.status == "covered"
    assert requirement.linked_tests == ["test_reset_password_email_flow"]


def test_build_requirement_coverages_marks_not_covered_when_no_match() -> None:
    """Criteria with no matching test should be marked as not_covered."""
    criteria = ["Nonexistent behaviour"]
    code = """
def test_unrelated(page):
    pass
"""
    requirements = build_requirement_coverages(criteria, code)
    assert len(requirements) == 1
    assert requirements[0].status == "not_covered"
    assert requirements[0].linked_tests == []


def test_build_coverage_analysis_wraps_requirements_list() -> None:
    """build_coverage_analysis should return a dict with requirements key."""
    criteria = ["A thing to test"]
    code = """
def test_01_a_thing_to_test(page):
    pass
"""
    analysis = build_coverage_analysis(criteria, code)
    assert "requirements" in analysis
    reqs = analysis["requirements"]
    assert len(reqs) == 1
    assert isinstance(reqs[0], RequirementCoverage)


def test_requirement_coverage_to_dict_round_trip() -> None:
    """RequirementCoverage.to_dict should preserve fields."""
    rc = RequirementCoverage(
        id="TC-001",
        description="Example description",
        status="covered",
        linked_tests=["test_example"],
    )
    as_dict = rc.to_dict()
    assert as_dict["id"] == "TC-001"
    assert as_dict["description"] == "Example description"
    assert as_dict["status"] == "covered"
    assert as_dict["linked_tests"] == ["test_example"]
