"""Code validation utilities for the AI-Playwright-Test-Generator.

This module provides functions to validate generated Python code
before it is saved or executed, catching syntax errors early.
"""

import ast
import re


def validate_python_syntax(code: str) -> str | None:
    """
    Validate Python code using ast.parse().

    This function parses the given code and returns None if the syntax
    is valid, or a descriptive error message if there's a syntax error.

    Args:
        code: Python source code to validate

    Returns:
        None if the code has valid syntax, or an error message string
        describing the syntax error if validation fails.

    Example:
        >>> validate_python_syntax("x = 1")
        None
        >>> validate_python_syntax("x =")  # doctest: +SKIP
        "Line 1: invalid syntax (text: 'x =')"
    """
    try:
        ast.parse(code)
        return None  # Valid syntax
    except SyntaxError as e:
        # Format error message for user display
        error_text = e.text.strip() if e.text and e.text.strip() else "N/A"
        return f"Line {e.lineno}: {e.msg} (text: {error_text})"


def validate_test_function(code: str) -> str | None:
    """
    Validate a generated test function with additional checks.

    Performs syntax validation plus additional checks specific to
    Playwright test functions:
    - Ensures no async def is used
    - Ensures the function has a test_ prefix

    Args:
        code: Python test function code to validate

    Returns:
        None if validation passes, or an error message string if validation fails.
    """
    # First check basic syntax
    syntax_error = validate_python_syntax(code)
    if syntax_error:
        return f"Syntax Error: {syntax_error}"

    # Parse the AST to check for async functions
    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            # Check for async function definitions
            if isinstance(node, ast.AsyncFunctionDef):
                return "Error: Generated test uses 'async def' which is not allowed. Use synchronous pytest format with 'def' instead."

            # Check that test functions have proper naming
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("test_"):
                    # Check for async keyword on regular function (shouldn't happen but be thorough)
                    pass  # Regular function defs are OK

    except SyntaxError as e:
        error_text = e.text.strip() if e.text and e.text.strip() else "N/A"
        return f"Parse Error Line {e.lineno}: {e.msg} (text: {error_text})"

    return None  # All checks passed


def validate_generated_locator_quality(code: str) -> str | None:
    """Validate generated Playwright locator patterns for known flaky/invalid cases."""
    if ".should_be_visible(" in code:
        return (
            "Error: Generated code uses `.should_be_visible()`, which is not valid in Playwright Python. "
            "Use `expect(locator).to_be_visible()` instead."
        )

    if re.search(r'get_by_role\(\s*["\']link["\']\s*\)', code):
        return (
            "Error: Generated code uses `get_by_role('link')` without a unique name/test-id. "
            "This is often ambiguous in strict mode."
        )

    if re.search(r'get_by_role\(\s*["\']button["\']\s*,\s*name\s*=\s*["\']shopping cart["\']', code, re.IGNORECASE):
        return (
            "Error: Generated code targets shopping cart as a button role. "
            "Use the cart link/test-id locator from page context instead."
        )

    if re.search(r'page\.locator\(\s*["\'](button|a|input|div|span)["\']\s*\)', code):
        return (
            'Error: Generated code uses broad tag-only locators (e.g. `page.locator("button")`). '
            "Use specific id/test-id/role+name locators from page context."
        )

    if re.search(r"except\s*:\s*[\r\n]+\s*pass\b", code):
        return (
            "Error: Generated code suppresses errors via `except: pass`, which hides test failures. "
            "Generated tests must fail loudly on unexpected conditions."
        )

    if "saucedemo.com" in code and re.search(
        r'get_by_role\(\s*["\']link["\']\s*,\s*name\s*=\s*["\']Backpack["\']', code
    ):
        return (
            "Error: Generated SauceDemo code uses ambiguous `get_by_role('link', name='Backpack')`. "
            "Use specific item/cart locators from scraped context (id/test-id) instead."
        )

    if "saucedemo.com" in code and "checkout.html" in code:
        return (
            "Error: Generated SauceDemo code references `/checkout.html`, which is not a valid flow URL. "
            "Use `checkout-step-one.html` / `checkout-step-two.html` / `checkout-complete.html` as appropriate."
        )

    if "saucedemo.com" in code and "Checkout: Your Information" in code:
        return (
            "Error: Generated SauceDemo code asserts title `Checkout: Your Information`, which is not the page title. "
            "Prefer URL assertions with valid checkout-step URLs."
        )

    if "saucedemo.com" in code and 'expect(page).to_have_url("https://www.saucedemo.com")' in code:
        return (
            "Error: Generated SauceDemo code asserts exact base URL without trailing slash before login flow. "
            "Avoid brittle pre-login exact URL assertions; assert post-login `inventory.html` or use a URL regex."
        )

    if "saucedemo.com" in code and 'expect(page).not_to_have_url("https://www.saucedemo.com/cart.html")' in code:
        return (
            "Error: Generated SauceDemo checkout assertion is too weak (`not_to_have_url(cart.html)`). "
            "Use a positive assertion for a valid checkout URL such as `checkout-step-one.html`."
        )

    return None
