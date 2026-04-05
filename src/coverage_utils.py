"""Utilities for requirement coverage analysis.

This module centralises the logic for turning acceptance criteria and
generated test code into structured coverage information that can be
reused by different frontends (Streamlit UI, CLI, reports).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RequirementCoverage:
    """Track coverage for a single requirement."""

    id: str
    description: str
    status: str  # "not_covered", "covered", "partial"
    linked_tests: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a serialisable representation of this requirement."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "linked_tests": list(self.linked_tests),
        }


class RunTestLike(Protocol):
    """Protocol for minimal test-run result objects used in coverage mapping."""

    name: str
    status: str
    duration: float


@dataclass
class CoverageDisplayRow:
    """Display-ready coverage row for UI tables."""

    id_cell: str
    requirement: str
    status: str
    tests: str
    result: str

    def to_dict(self) -> dict[str, str]:
        """Convert row into a Streamlit dataframe-friendly dictionary."""
        return {
            "ID": self.id_cell,
            "Requirement": self.requirement,
            "Status": self.status,
            "Tests": self.tests,
            "Result": self.result,
        }


_TEST_DEF_pattern = re.compile(r"^def (test_\w+)", re.MULTILINE)


def extract_test_names(generated_code: str) -> list[str]:
    """Extract pytest-style test function names from Python source code."""
    if not generated_code:
        return []
    return _TEST_DEF_pattern.findall(generated_code)


def build_requirement_coverages(
    acceptance_criteria_lines: list[str],
    generated_code: str,
) -> list[RequirementCoverage]:
    """Build RequirementCoverage objects from criteria and generated test code."""
    test_names = extract_test_names(generated_code)
    requirements: list[RequirementCoverage] = []
    for index, criterion in enumerate(acceptance_criteria_lines, start=1):
        req_id = f"TC-{index:03d}"
        num_str = f"{index:02d}"
        linked = [name for name in test_names if f"test_{num_str}_" in name or f"test_{index}_" in name]
        if not linked:
            words = {word for word in criterion.lower().split() if word}
            linked = [name for name in test_names if len(words & set(name.lower().split("_"))) >= 2]
        status = "covered" if linked else "not_covered"
        requirements.append(
            RequirementCoverage(
                id=req_id,
                description=criterion,
                status=status,
                linked_tests=linked,
            )
        )
    return requirements


def build_coverage_analysis(
    acceptance_criteria_lines: list[str],
    generated_code: str,
) -> dict[str, list[RequirementCoverage]]:
    """Return the coverage analysis dict used by UIs and report builders."""
    return {"requirements": build_requirement_coverages(acceptance_criteria_lines, generated_code)}


def _status_emoji(status: str) -> str:
    """Return a visual status marker for requirement coverage status."""
    if status == "covered":
        return "✅"
    if status == "partial":
        return "⚠️"
    return "❌"


def _result_icon(status: str) -> str:
    """Return run-result icon for a single linked test status."""
    if status == "passed":
        return "✅"
    if status == "failed":
        return "❌"
    if status == "skipped":
        return "⏭️"
    return "⏳"


def build_coverage_display_rows(
    requirements: list[RequirementCoverage],
    run_results: Sequence[RunTestLike] | None = None,
) -> list[CoverageDisplayRow]:
    """Build display-ready rows from RequirementCoverage objects.

    Args:
        requirements: List of RequirementCoverage objects.
        run_results: Optional sequence of run result objects satisfying RunTestLike.

    Returns:
        List of CoverageDisplayRow objects ready for UI table rendering.
    """
    # Build a lookup from base test name to run status.
    # pytest appends [chromium] etc., so we strip the bracket suffix for matching.
    run_map: dict[str, str] = {}
    if run_results:
        for tr in run_results:
            base_name = tr.name.split("[")[0]
            run_map[base_name] = tr.status

    rows: list[CoverageDisplayRow] = []
    for req in requirements:
        status_emoji = _status_emoji(req.status)
        id_cell = f"{status_emoji} {req.id}"
        status_label = req.status.upper()

        tests_cell = "; ".join(req.linked_tests[:3])
        if len(req.linked_tests) > 3:
            tests_cell += "..."

        # Build result cell from run_results if available.
        result_cell = ""
        if run_results is not None and req.linked_tests:
            icons: list[str] = []
            for test_name in req.linked_tests:
                base_name = test_name.split("[")[0]
                if base_name in run_map:
                    icons.append(_result_icon(run_map[base_name]))
                # If linked test not found in run map, emit nothing (test not yet run).
            result_cell = ", ".join(icons)

        rows.append(
            CoverageDisplayRow(
                id_cell=id_cell,
                requirement=req.description,
                status=status_label,
                tests=tests_cell,
                result=result_cell,
            )
        )

    return rows
