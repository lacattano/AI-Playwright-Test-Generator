"""Unit tests for run_utils module."""

from __future__ import annotations

from dataclasses import dataclass

from src.run_utils import build_pytest_run_command, extract_failed_nodeids_from_raw_output, get_failed_nodeids


@dataclass
class _TestResult:
    name: str
    status: str
    file_path: str


def test_get_failed_nodeids_returns_empty_for_none() -> None:
    """No run result means no failed nodeids."""
    assert get_failed_nodeids(None) == []


def test_get_failed_nodeids_extracts_failed_only_and_deduplicates() -> None:
    """Only failed tests should be included once in returned nodeids."""
    run_results = [
        _TestResult(name="test_a[chromium]", status="passed", file_path="generated_tests/test_file.py"),
        _TestResult(name="test_b[chromium]", status="failed", file_path="generated_tests/test_file.py"),
        _TestResult(name="test_b[chromium]", status="failed", file_path="generated_tests/test_file.py"),
        _TestResult(name="test_c[chromium]", status="failed", file_path="generated_tests/test_other.py"),
    ]
    nodeids = get_failed_nodeids(run_results)
    assert nodeids == [
        "generated_tests/test_file.py::test_b[chromium]",
        "generated_tests/test_other.py::test_c[chromium]",
    ]


def test_build_pytest_run_command_defaults_to_saved_path() -> None:
    """Command should target saved path when no failed list is supplied."""
    command = build_pytest_run_command("generated_tests/test_file.py")
    assert command[-1] == "generated_tests/test_file.py"
    assert command[0] == "pytest"
    assert "--browser=chromium" in command


def test_build_pytest_run_command_uses_failed_nodeids_when_present() -> None:
    """Failed-only rerun should target explicit failed nodeids."""
    nodeids = ["generated_tests/test_file.py::test_b[chromium]"]
    command = build_pytest_run_command("generated_tests/test_file.py", failed_nodeids=nodeids)
    assert command[-1] == "generated_tests/test_file.py::test_b[chromium]"
    assert "generated_tests/test_file.py" not in command


def test_extract_failed_nodeids_from_raw_output_returns_unique_failed_items() -> None:
    """Raw pytest lines should produce deduplicated failed nodeids for rerun."""
    raw_output = """
generated_tests/test_flow.py::test_a[chromium] PASSED [ 16%]
generated_tests/test_flow.py::test_b[chromium] FAILED [ 33%]
generated_tests/test_flow.py::test_c[chromium] FAILED [ 50%]
generated_tests/test_flow.py::test_b[chromium] FAILED [ 66%]
"""
    nodeids = extract_failed_nodeids_from_raw_output(raw_output)
    assert nodeids == [
        "generated_tests/test_flow.py::test_b[chromium]",
        "generated_tests/test_flow.py::test_c[chromium]",
    ]
