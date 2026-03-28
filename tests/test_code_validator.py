"""Unit tests for the code_validator module."""

from src.code_validator import validate_python_syntax, validate_test_function


class TestValidatePythonSyntax:
    """Test cases for validate_python_syntax function."""

    def test_valid_simple_assignment(self) -> None:
        """Test validation of a simple valid assignment."""
        result = validate_python_syntax("x = 1")
        assert result is None

    def test_valid_function_definition(self) -> None:
        """Test validation of a valid function definition."""
        code = """
def hello():
    print("Hello, World!")
"""
        result = validate_python_syntax(code)
        assert result is None

    def test_valid_import_statements(self) -> None:
        """Test validation of valid import statements."""
        code = """
from playwright.sync_api import sync_playwright
import pytest
"""
        result = validate_python_syntax(code)
        assert result is None

    def test_invalid_missing_colon(self) -> None:
        """Test detection of missing colon in function definition."""
        result = validate_python_syntax("def test_hello()")
        assert result is not None
        assert "Line 1" in result
        assert "expected ':'" in result

    def test_invalid_missing_closing_parenthesis(self) -> None:
        """Test detection of missing closing parenthesis."""
        result = validate_python_syntax("print(")
        assert result is not None
        assert "Line 1" in result

    def test_invalid_invalid_indentation(self) -> None:
        """Test detection of invalid indentation."""
        code = """
def test_hello():
    print("hello")
  print("bad indent")
"""
        result = validate_python_syntax(code)
        assert result is not None

    def test_invalid_unclosed_string(self) -> None:
        """Test detection of unclosed string literal."""
        result = validate_python_syntax('print("hello')
        assert result is not None
        assert "Line 1" in result

    def test_valid_empty_code(self) -> None:
        """Test that empty code is valid."""
        result = validate_python_syntax("")
        assert result is None

    def test_valid_multiline_code(self) -> None:
        """Test validation of multiline valid code."""
        code = """
def test_example():
    x = 1
    y = 2
    assert x + y == 3
"""
        result = validate_python_syntax(code)
        assert result is None

    def test_error_message_includes_line_number(self) -> None:
        """Test that error message includes the correct line number."""
        code = """
x = 1
y =
z = 3
"""
        result = validate_python_syntax(code)
        assert result is not None
        assert "Line 3" in result  # The error is on line 3 where 'y =' is incomplete (line 1 is the leading newline)

    def test_error_message_includes_text(self) -> None:
        """Test that error message includes the problematic text."""
        result = validate_python_syntax("x =")
        assert result is not None
        assert "x =" in result


class TestValidateTestFunction:
    """Test cases for validate_test_function function."""

    def test_valid_sync_test_function(self) -> None:
        """Test validation of a valid synchronous test function."""
        code = """
def test_login(page):
    page.goto("https://example.com")
    page.fill("input[name='email']", "test@example.com")
"""
        result = validate_test_function(code)
        assert result is None

    def test_invalid_async_test_function(self) -> None:
        """Test detection of async def in test function."""
        code = """
async def test_login(page):
    await page.goto("https://example.com")
"""
        result = validate_test_function(code)
        assert result is not None
        assert "async def" in result
        assert "not allowed" in result

    def test_invalid_syntax_catches_first(self) -> None:
        """Test that syntax errors are caught before async check."""
        code = """
def test_hello(
    print("missing closing paren")
"""
        result = validate_test_function(code)
        assert result is not None
        assert "Syntax Error" in result

    def test_valid_complex_test_with_assertions(self) -> None:
        """Test validation of a complex but valid test function."""
        code = """
def test_complete_workflow(page):
    page.goto("https://example.com")

    # Fill form
    page.fill("input[name='email']", "test@example.com")
    page.fill("input[name='password']", "password123")

    # Click submit
    page.click("button[type='submit']")

    # Verify
    page.wait_for_selector("div.success")
"""
        result = validate_test_function(code)
        assert result is None

    def test_valid_test_with_playwright_imports(self) -> None:
        """Test that imports in test functions are handled correctly."""
        code = """
from playwright.sync_api import expect

def test_with_expect(page):
    page.goto("https://example.com")
    expect(page.locator("h1")).to_contain_text("Hello")
"""
        result = validate_test_function(code)
        assert result is None

    def test_multiple_functions_valid(self) -> None:
        """Test validation of multiple valid test functions."""
        code = """
def test_first(page):
    page.goto("https://example.com")

def test_second(page):
    page.fill("input", "value")
"""
        result = validate_test_function(code)
        assert result is None

    def test_nested_async_in_lambda_not_detected(self) -> None:
        """Test that async in lambda within code is not incorrectly flagged.

        Note: This is edge case behavior - AST walks all nodes including lambdas.
        """
        # This test documents current behavior - async lambdas would be flagged
        code = """
def test_with_lambda(page):
    x = lambda: None
    page.goto("https://example.com")
"""
        result = validate_test_function(code)
        assert result is None  # Regular function with lambda should be OK
