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


_TEST_DEF_PATTERN = re.compile(r"^def (test_\w+)", re.MULTILINE)


def extract_test_names(generated_code: str) -> list[str]:
    """Extract pytest-style test function names from Python source code.

    Args:
        generated_code: Python code containing test function definitions.

    Returns:
        List of test function names (e.g. ``['test_01_login', 'test_02_logout']``).
    """
    if not generated_code:
        return []
    return _TEST_DEF_PATTERN.findall(generated_code)


def build_requirement_coverages(
    acceptance_criteria_lines: list[str],
    generated_code: str,
) -> list[RequirementCoverage]:
    """Build RequirementCoverage objects from criteria and generated test code.

    The behaviour mirrors the original inline implementation in ``streamlit_app``
    so existing coverage semantics are preserved:

    - Requirements are numbered sequentially as ``TC-001``, ``TC-002``, ...
    - Primary matching uses the test name pattern ``test_<num>_`` where
      ``<num>`` is either zero-padded (``01``) or plain (``1``).
    - Fallback matching uses word overlap between the criterion text and the
      test function name (at least two shared words).
    - Status is ``\"covered\"`` when one or more linked tests are found,
      otherwise ``\"not_covered\"``.

    Args:
        acceptance_criteria_lines: Ordered list of acceptance criteria text.
        generated_code: Generated Python test code.

    Returns:
        List of RequirementCoverage instances in the same order as the criteria.
    """
    test_names = extract_test_names(generated_code)
    requirements: list[RequirementCoverage] = []

    for index, criterion in enumerate(acceptance_criteria_lines, start=1):
        req_id = f"TC-{index:03}"
        num_str = f"{index:02}"

        # Primary: explicit numbering in test name
        linked = [name for name in test_names if f"test_{num_str}_" in name or f"test_{index}_" in name]

        # Fallback: word overlap between criterion and test name
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
    return "⏳"


def build_coverage_display_rows(
    requirements: list[RequirementCoverage],
    run_results: Sequence[RunTestLike] | None = None,
) -> list[CoverageDisplayRow]:
    """Build UI display rows for coverage table, optionally enriched with run results."""
    run_map: dict[str, RunTestLike] = {}
    if run_results:
        run_map = {result.name: result for result in run_results}

    rows: list[CoverageDisplayRow] = []
    for requirement in requirements:
        result_cell = ""
        if run_map:
            icons: list[str] = []
            for test_name in requirement.linked_tests:
                matched = next(
                    (
                        result
                        for result_name, result in run_map.items()
                        if result_name == test_name or result_name.startswith(test_name)
                    ),
                    None,
                )
                if matched is None:
                    icons.append("⏳")
                else:
                    icons.append(_result_icon(matched.status))
            result_cell = ", ".join(icons)

        linked_tests_text = "; ".join(requirement.linked_tests[:3])
        if len(requirement.linked_tests) > 3:
            linked_tests_text += "..."

        rows.append(
            CoverageDisplayRow(
                id_cell=f"{_status_emoji(requirement.status)} {requirement.id}",
                requirement=requirement.description,
                status=requirement.status.upper(),
                tests=linked_tests_text,
                result=result_cell,
            )
        )

    return rows
