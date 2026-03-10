"""
pytest_output_parser.py — Parse pytest output into structured results

This module provides utilities to parse pytest text stdout output and return
structured test execution results for coverage reporting.

No external dependencies - only uses Python standard library.
Fully unit testable with real pytest output strings as fixtures.
"""

import re
from dataclasses import dataclass


@dataclass
class TestResult:
    """Represents the result of a single test case."""

    name: str  # "test_01_login_page_displayed"
    status: str  # "passed", "failed", "error"
    duration: float  # seconds, 0.0 if not available
    error_message: str  # "" if passed, short error if failed
    file_path: str  # relative path to test file


@dataclass
class RunResult:
    """Represents a complete test run result."""

    results: list[TestResult]
    total: int
    passed: int
    failed: int
    errors: int
    duration: float  # total run duration in seconds
    raw_output: str  # preserve original for expander


def parse_pytest_output(raw: str) -> RunResult:
    """
    Parse raw pytest -v output into structured RunResult.

    Handles these pytest output patterns:

    PASSED line:
      test_file.py::test_01_login_page_displayed PASSED [ 50%]

    FAILED line:
      test_file.py::test_02_inventory FAILED [100%]

    Duration line (at end):
      2 passed, 1 failed in 3.45s
      3 passed in 1.20s

    Error message (after FAILED):
      FAILED test_file.py::test_name - AssertionError: expected...

    Args:
        raw: Raw pytest stdout output string

    Returns:
        RunResult with all parsed test data
    """
    PASSED_RE = re.compile(r"(\S+\.py)::(\S+)\s+PASSED\s+\[")
    FAILED_RE = re.compile(r"(\S+\.py)::(\S+)\s+FAILED\s+\[")
    DURATION_RE = re.compile(r"(\d+) passed(?:, (\d+) failed)? in ([\d.]+)s")
    # Match lines like "===FAILURES===" or "__________test_name__________"
    FAILURE_BLOCK_RE = re.compile(
        r"^={30,}[\s]*FAILURES[\s]*={30,}$",
        re.IGNORECASE,
    )
    STACK_TRACE_LINE_RE = re.compile(
        r"^\s*(?:(await|return)\s+)?[a-zA-Z_][\w]*(?:\s*\.\s*[a-zA-Z_][\w]*)*(?:\s*\([^)]*\))?\s*$"
    )

    lines = raw.splitlines()
    results: list[TestResult] = []
    failed_tests: dict[str, TestResult] = {}  # Track failed tests for error attachment
    in_failure_block = False
    current_failed_test_name: str | None = None
    failure_block_lines: list[str] = []

    def finalize_current_failure() -> None:
        """Process collected lines to extract error message for current failing test."""
        nonlocal current_failed_test_name, failure_block_lines, in_failure_block
        if not current_failed_test_name or not failure_block_lines:
            return

        # Join all lines and search for assertion/timeout error
        full_text = "\n".join(failure_block_lines)

        # Look for "AssertionError: message" pattern - handle both cases:
        # 1. "path::test - AssertionError: message" (inline with dash before)
        # 2. "AssertionError: message" (just the error, no leading text)
        assertion_match = re.search(
            r"(?:-\s*)?(?:[\w.]*\.)?(?P<error>AssertionError|TimeoutError|ValueError|AttributeError|KeyError|Error):\s*(?P<message>.+)$",
            full_text,
            re.MULTILINE | re.DOTALL,
        )

        if assertion_match:
            error_msg = assertion_match.group("message").strip().splitlines()[0]
            test_result = failed_tests.get(current_failed_test_name)
            if test_result:
                test_result.error_message = error_msg

        # Clean up state
        failure_block_lines = []
        current_failed_test_name = None

    def process_failure_block_line(line: str) -> bool:
        """Process a line inside failure block. Returns True if should continue."""
        nonlocal in_failure_block, current_failed_test_name, failure_block_lines

        stripped_line = line.strip()

        # Match patterns like "__ test_name __" as separators between failures
        new_failure_sep = re.match(r"_{2,} +(\S+) +_{2,}", stripped_line)
        if new_failure_sep:
            test_name = new_failure_sep.group(1)
            # Save previous one first
            finalize_current_failure()
            # Start new one
            current_failed_test_name = test_name
            failure_block_lines = []
            return True

        # Check if this line starts a new section (leaving failure block)
        new_section_re = re.compile(r"^(===.*=+|_{3,}\s*PASSED\s*$|collected\s+\d+)")
        if new_section_re.match(line):
            finalize_current_failure()
            in_failure_block = False
            return False

        # Collect stack trace lines and error messages for later parsing
        # Lines starting with whitespace or line numbers are part of failure details
        if line.startswith(" ") or re.match(r"^\s*\d+:", line):
            failure_block_lines.append(line)
        elif STACK_TRACE_LINE_RE.match(line.strip()):
            failure_block_lines.append(line)
        else:
            # Capture any other lines that aren't section headers (e.g., "AssertionError: ...")
            # These are likely error messages or traceback details
            error_line_re = re.compile(r"^(?:[a-zA-Z_][\w.]*\.)?[A-Z][a-zA-Z]+Error:")
            if error_line_re.match(stripped_line):
                failure_block_lines.append(line)

        return True

    for line in lines:
        # Track when we enter a FAILURE block
        if FAILURE_BLOCK_RE.match(line):
            in_failure_block = True
            continue

        # Check for PASSED pattern
        passed_match = PASSED_RE.search(line)
        if passed_match:
            file_path, test_name = passed_match.groups()
            result = TestResult(name=test_name, status="passed", duration=0.0, error_message="", file_path=file_path)
            results.append(result)
            continue

        # Check for FAILED pattern (no inline error message in the summary line)
        failed_match = FAILED_RE.search(line)
        if failed_match:
            file_path, test_name = failed_match.groups()
            result = TestResult(name=test_name, status="failed", duration=0.0, error_message="", file_path=file_path)
            results.append(result)
            failed_tests[test_name] = result
            # Will be populated by failure block processing
            continue

        # Process lines inside failure block
        if in_failure_block:
            if not process_failure_block_line(line):
                in_failure_block = False
            continue

    # Extract duration from pytest summary line (e.g., "2 passed, 1 failed in 3.45s" or "3 passed in 2.10s")
    total_duration = 0.0
    duration_match = DURATION_RE.search(raw)
    if duration_match:
        _, _, total_seconds = duration_match.groups()
        total_duration = float(total_seconds)

    simple_duration_re = re.compile(r"(\d+) passed in ([\d.]+)s")
    simple_match = simple_duration_re.search(raw)
    if simple_match:
        _, total_seconds = simple_match.groups()
        total_duration = max(total_duration, float(total_seconds))

    # Derive counts directly from parsed results - this is the authoritative source
    passed_count = sum(1 for r in results if r.status == "passed")
    failed_count = sum(1 for r in results if r.status == "failed")
    error_count = sum(1 for r in results if r.status == "error")

    return RunResult(
        results=results,
        total=len(results),
        passed=passed_count,
        failed=failed_count,
        errors=error_count,
        duration=total_duration,
        raw_output=raw,
    )


def extract_error_message(raw: str) -> str:
    """
    Extract error message from failed test output.

    Args:
        raw: Raw pytest output string

    Returns:
        Error message or empty string if not found
    """
    ERROR_RE = re.compile(r"FAILED\s+\S+::\S+\s+-\s+(.+)")
    match = ERROR_RE.search(raw)
    if match:
        return match.group(1).strip()
    return ""
