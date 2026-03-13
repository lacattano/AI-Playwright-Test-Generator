"""Unit tests for LLM error helper structures."""

from __future__ import annotations

from src.llm_errors import LLMError, LLMErrorType, LLMResult


def test_llm_error_enum_values() -> None:
    """LLMErrorType should expose expected members."""
    assert LLMErrorType.EMPTY_RESPONSE.value == "empty_response"
    assert LLMErrorType.UNKNOWN.value == "unknown"


def test_llm_result_with_code_has_no_error() -> None:
    """LLMResult with code populated should have no error."""
    result = LLMResult(code="print('ok')")
    assert result.code == "print('ok')"
    assert result.error is None


def test_llm_result_with_error_has_no_code() -> None:
    """LLMResult with error should allow code to be None."""
    error = LLMError(error_type=LLMErrorType.EMPTY_RESPONSE, message="Empty response")
    result = LLMResult(code=None, error=error)
    assert result.code is None
    assert result.error is error
