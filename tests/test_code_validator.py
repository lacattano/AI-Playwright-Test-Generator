"""Unit tests for the code_validator module."""

from src.code_validator import (
    validate_generated_locator_quality,
    validate_python_syntax,
    validate_test_function,
)


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


class TestValidateGeneratedLocatorQuality:
    """Tests for generation-time locator quality heuristics."""

    def test_rejects_should_be_visible_pattern(self) -> None:
        """`.should_be_visible()` should be rejected as invalid Playwright Python."""
        code = """
def test_a(page):
    page.locator("#x").should_be_visible()
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "should_be_visible" in result

    def test_rejects_bare_link_role_locator(self) -> None:
        """`get_by_role('link')` without name should be rejected."""
        code = """
def test_a(page):
    page.get_by_role("link").click()
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "get_by_role('link')" in result

    def test_accepts_named_button_role_locator(self) -> None:
        """Named role locators are valid and should pass."""
        code = """
def test_a(page):
    page.get_by_role("button", name="shopping cart").click()
"""
        result = validate_generated_locator_quality(code)
        assert result is None

    def test_accepts_named_link_role_locator(self) -> None:
        """Named link role locator should not be rejected by generic checks."""
        code = """
def test_a(page):
    page.get_by_role("link", name="Products").click()
"""
        result = validate_generated_locator_quality(code)
        assert result is None

    def test_accepts_specific_id_or_testid_locators(self) -> None:
        """Specific locators should pass quality checks."""
        code = """
from playwright.sync_api import expect

def test_a(page):
    page.locator("#user-name").fill("standard_user")
    expect(page.get_by_test_id("shopping-cart-link")).to_be_visible()
"""
        result = validate_generated_locator_quality(code)
        assert result is None

    def test_rejects_broad_tag_only_locator(self) -> None:
        """Broad tag-only locator usage should be rejected."""
        code = """
def test_a(page):
    page.locator("button").click()
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "broad tag-only locators" in result

    def test_rejects_bare_except_pass(self) -> None:
        """Swallowed failures via except: pass should be rejected."""
        code = """
def test_a(page):
    try:
        page.locator("#x").click()
    except:
        pass
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "except: pass" in result

    def test_accepts_generic_url_assertion(self) -> None:
        """Positive exact URL assertions are valid in generic mode."""
        code = """
from playwright.sync_api import expect

def test_navigation(page):
    page.goto("https://example.com")
    expect(page).to_have_url("https://example.com/dashboard")
"""
        result = validate_generated_locator_quality(code)
        assert result is None

    def test_accepts_generic_title_assertion(self) -> None:
        """Title assertion is a valid generic assertion pattern."""
        code = """
from playwright.sync_api import expect

def test_page_title(page):
    page.goto("https://example.com")
    expect(page).to_have_title("Example Domain")
"""
        result = validate_generated_locator_quality(code)
        assert result is None

    def test_rejects_root_url_assertion_without_trailing_slash(self) -> None:
        """Reject root URL assertions missing the canonical trailing slash."""
        code = """
from playwright.sync_api import expect

def test_login(page):
    page.goto("https://example.com")
    expect(page).to_have_url("https://example.com")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "trailing slash" in result

    def test_rejects_custom_screenshot_markers(self) -> None:
        """Reject custom screenshot helpers and unknown pytest marks."""
        code = """
import pytest
from playwright.sync_api import Page, expect, screenshot

@pytest.mark.screenshot
def test_screenshot(page: Page):
    page.goto("https://example.com/")
    expect(page).to_have_url("https://example.com/")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "screenshot" in result

    def test_rejects_weak_negative_checkout_url_assertion(self) -> None:
        """Negative-only URL assertions should be rejected as weak signal."""
        code = """
from playwright.sync_api import expect

def test_checkout(page):
    page.goto("https://example.com/cart")
    page.locator("#checkout").click()
    expect(page).not_to_have_url("https://example.com/cart")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "negative-only URL assertions" in result

    def test_rejects_wait_for_load_state_status_usage(self) -> None:
        """Reject invalid Playwright API usage that assumes a response object."""
        code = """
def test_page_load(page):
    page.goto("https://example.com")
    response = page.wait_for_load_state("domcontentloaded", timeout=30000)
    assert response.status == 200
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "wait_for_load_state" in result

    def test_rejects_sync_playwright_fixtureless_usage(self) -> None:
        """Reject generated code that uses sync_playwright instead of pytest fixtures."""
        code = """
from playwright.sync_api import sync_playwright

def test_open_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto("https://example.com")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "sync_playwright" in result

    def test_rejects_invalid_url_containing_assertion(self) -> None:
        """Invalid Playwright `to_have_url_containing` usage should be rejected."""
        code = """
def test_page_load(page):
    page.goto("https://example.com")
    expect(page).to_have_url_containing("example.com")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "to_have_url_containing" in result

    def test_rejects_invalid_title_containing_assertion(self) -> None:
        """Invalid Playwright `to_have_title_containing` usage should be rejected."""
        code = """
def test_page_title(page):
    page.goto("https://example.com")
    expect(page).to_have_title_containing("Example")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "to_have_title_containing" in result

    def test_rejects_expect_page_title_call_usage(self) -> None:
        """Reject invalid `expect(page.title())` usage."""
        code = """
from playwright.sync_api import expect

def test_page_title(page):
    page.goto("https://example.com")
    expect(page.title()).to_contain("Example Domain")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "expect(page.title())" in result

    def test_rejects_expect_page_url_call_usage(self) -> None:
        """Reject invalid `expect(page.url())` usage."""
        code = """
from playwright.sync_api import expect

def test_page_url(page):
    page.goto("https://example.com")
    expect(page.url()).to_be("https://example.com")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "expect(page.url())" in result

    def test_rejects_re_compile_without_import(self) -> None:
        """Reject regex assertions that omit the import re statement."""
        code = """
from playwright.sync_api import expect

def test_page_title(page):
    page.goto("https://example.com")
    expect(page).to_have_title(re.compile(r"^Example Domain$"))
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "re.compile" in result

    def test_rejects_expect_without_import(self) -> None:
        """Generated code must import expect from playwright.sync_api when it is used."""
        code = """
def test_page_title(page):
    page.goto("https://example.com")
    expect(page).to_have_title("Example Domain")
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "does not import `expect`" in result

    def test_rejects_to_be_connected_usage(self) -> None:
        """Reject invalid expect(page).to_be_connected() usage."""
        code = """
from playwright.sync_api import expect

def test_page_load(page):
    page.goto("https://example.com")
    expect(page).to_be_connected()
"""
        result = validate_generated_locator_quality(code)
        assert result is not None
        assert "to_be_connected" in result
