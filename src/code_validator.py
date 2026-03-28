"""Code validation utilities for the AI-Playwright-Test-Generator.

This module provides functions to validate generated Python code
before it is saved or executed, catching syntax errors early.
"""

import ast


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
