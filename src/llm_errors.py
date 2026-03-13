"""Lightweight error structures for LLM-backed test generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LLMErrorType(StrEnum):
    """High-level categories for LLM failures."""

    EMPTY_RESPONSE = "empty_response"
    UNKNOWN = "unknown"


@dataclass
class LLMError:
    """Structured error information for callers."""

    error_type: LLMErrorType
    message: str


@dataclass
class LLMResult:
    """Wrapper for LLM generation results."""

    code: str | None
    error: LLMError | None = None
