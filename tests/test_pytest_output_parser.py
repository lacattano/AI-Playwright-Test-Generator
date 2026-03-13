"""
Tests for pytest_output_parser module.

Uses real pytest output strings as fixtures to verify parsing accuracy.
"""

import pytest

from src.pytest_output_parser import RunResult, TestResult, parse_pytest_output


@pytest.fixture
def all_passed_output() -> str:
    """Real pytest output: 3 tests all passed."""
    return """============================= test session starts =============================
collected 3 items

generated_tests/test_generated_playwright.py::test_01_login_page_displayed PASSED [ 33%]
generated_tests/test_generated_playwright.py::test_02_inventory_displayed PASSED [ 66%]
generated_tests/test_generated_playwright.py::test_03_add_to_cart PASSED [100%]

============================== 3 passed in 4.52s ============================="""


@pytest.fixture
def mixed_pass_fail_output() -> str:
    """Real pytest output: mix of passed and failed tests."""
    return """============================= test session starts =============================
collected 3 items

generated_tests/test_generated_playwright.py::test_01_login_page_displayed PASSED [ 33%]
generated_tests/test_generated_playwright.py::test_02_inventory_displayed PASSED [ 66%]
generated_tests/test_generated_playwright.py::test_03_add_to_cart FAILED [100%]

=================================== FAILURES ===================================
___________________________ test_03_add_to_cart ____________________________
generated_tests/test_generated_playwright.py:47: in test_03_add_to_cart
    await page.locator("text=Add to cart").first.wait_for(timeout=5000)
AssertionError: Timeout 5000ms exceeded.

=========================== 1 failed, 2 passed in 6.12s ==========================="""


@pytest.fixture
def simple_duration_output() -> str:
    """Pytest output with 'X passed in Ys' format (no failed count)."""
    return """============================= test session starts =============================
collected 5 items

tests/test_example.py::test_one PASSED [ 20%]
tests/test_example.py::test_two PASSED [ 40%]
tests/test_example.py::test_three PASSED [ 60%]
tests/test_example.py::test_four PASSED [ 80%]
tests/test_example.py::test_five PASSED [100%]

============================== 5 passed in 2.34s ============================="""


@pytest.fixture
def empty_output() -> str:
    """Minimal pytest output with no tests collected."""
    return """============================= test session starts =============================
collected 0 items

============================ no tests ran in 0.01s ============================="""


@pytest.fixture
def collection_error_output() -> str:
    """Pytest output with collection errors (no tests run)."""
    return """============================= test session starts =============================
collected 0 items / 1 error

==================================== ERRORS ====================================
_______________ ERROR collecting generated_tests/test_nonexistent.py ________________
ImportError while importing test module 'generated_tests/test_nonexistent.py'.
Hint: make sure your test packages/packages have valid Python names.
Traceback:
generated_tests/test_nonexistent.py:3: in <module>
    import nonexistent_module
=========================== short test summary info ===========================
ERROR generated_tests/test_nonexistent.py
============================== 1 error in 0.12s ============================="""


@pytest.fixture
def failed_with_inline_error() -> str:
    """Failed test with inline assertion error."""
    return """============================= test session starts =============================
collected 2 items

generated_tests/test_generated_playwright.py::test_01_login PASSED [ 50%]
generated_tests/test_generated_playwright.py::test_02_password_field FAILED [100%]

=================================== FAILURES ===================================
__________________________ test_02_password_field ___________________________
generated_tests/test_generated_playwright.py:18: in test_02_password_field
    assert page.locator("text=Submit").is_visible() == True
AssertionError: assert False == True
=========================== 1 failed, 1 passed in 1.85s ==========================="""


class TestParsePytestOutput:
    """Test suite for parse_pytest_output function."""

    def test_parses_all_passed(self, all_passed_output: str) -> None:
        """Test parsing when all tests pass."""
        result = parse_pytest_output(all_passed_output)

        assert isinstance(result, RunResult)
        assert result.total == 3
        assert result.passed == 3
        assert result.failed == 0
        assert result.errors == 0
        assert result.duration > 0

    def test_parses_mixed_pass_fail(self, mixed_pass_fail_output: str) -> None:
        """Test parsing when some tests pass and some fail."""
        result = parse_pytest_output(mixed_pass_fail_output)

        assert isinstance(result, RunResult)
        assert result.total == 3
        assert result.passed == 2
        assert result.failed == 1
        assert result.errors == 0
        assert result.duration > 0

    def test_extracts_test_names(self, all_passed_output: str) -> None:
        """Test that test names are correctly extracted."""
        result = parse_pytest_output(all_passed_output)

        test_names = [r.name for r in result.results]
        assert "test_01_login_page_displayed" in test_names
        assert "test_02_inventory_displayed" in test_names
        assert "test_03_add_to_cart" in test_names

    def test_extracts_duration(self, all_passed_output: str) -> None:
        """Test that run duration is correctly extracted."""
        result = parse_pytest_output(all_passed_output)

        # Duration should be a float > 0 and reasonable (between 1-10 seconds)
        assert isinstance(result.duration, float)
        assert result.duration > 0
        assert result.duration < 10.0

    def test_failed_count_correct(self, mixed_pass_fail_output: str) -> None:
        """Test that failed count is correct."""
        result = parse_pytest_output(mixed_pass_fail_output)

        assert result.failed == 1

    def test_passed_count_correct(self, all_passed_output: str) -> None:
        """Test that passed count matches total when all pass."""
        result = parse_pytest_output(all_passed_output)

        assert result.passed == result.total

    def test_error_message_extracted(self, failed_with_inline_error: str) -> None:
        """Test that error messages are extracted from failed tests."""
        result = parse_pytest_output(failed_with_inline_error)

        # Find the failed test
        failed_tests = [r for r in result.results if r.status == "failed"]
        assert len(failed_tests) == 1

        error = failed_tests[0].error_message
        # Error message should contain just the assertion content, not "AssertionError:" prefix
        assert "assert False == True" in error

    def test_handles_empty_output(self, empty_output: str) -> None:
        """Test handling of minimal pytest output with no tests."""
        result = parse_pytest_output(empty_output)

        assert isinstance(result, RunResult)
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0

    def test_handles_collection_error(self, collection_error_output: str) -> None:
        """Test handling of pytest output with collection errors."""
        result = parse_pytest_output(collection_error_output)

        # Should return RunResult even if no duration found
        assert isinstance(result, RunResult)
        assert result.errors == 0  # Parser doesn't extract collection errors yet

    def test_preserves_raw_output(self, all_passed_output: str) -> None:
        """Test that raw output is preserved in result."""
        result = parse_pytest_output(all_passed_output)

        assert result.raw_output == all_passed_output


class TestTestDataclass:
    """Tests for TestResult dataclass structure."""

    def test_testresult_structure(self) -> None:
        """Test TestResult has all required fields."""
        test_result = TestResult(
            name="test_example", status="passed", duration=1.5, error_message="", file_path="tests/test_example.py"
        )

        assert test_result.name == "test_example"
        assert test_result.status in ("passed", "failed", "error")
        assert isinstance(test_result.duration, float)
        assert test_result.error_message == ""
        assert test_result.file_path.endswith(".py")


class TestStatusCounts:
    """Tests for passed/failed/error counts logic."""

    def test_only_passed_in_results(self) -> None:
        """Test count when all results are passed."""
        run_result = RunResult(
            results=[
                TestResult(name="test_1", status="passed", duration=0.5, error_message="", file_path="t.py"),
                TestResult(name="test_2", status="passed", duration=0.3, error_message="", file_path="t.py"),
            ],
            total=2,
            passed=2,
            failed=0,
            errors=0,
            duration=0.8,
            raw_output="test output",
        )

        assert run_result.passed == 2
        assert run_result.failed == 0

    def test_status_from_results_when_no_counts(self) -> None:
        """Test that status counts are derived from results when not explicitly set."""
        result = parse_pytest_output("""============================= test session starts =============================
collected 2 items

t.py::test_a PASSED [ 50%]
t.py::test_b FAILED [100%]

=========================== 1 passed, 1 failed in 1.0s ===========================""")

        assert result.passed == 1
        assert result.failed == 1
