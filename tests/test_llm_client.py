"""Unit tests for the LLM client module.

Tests verify prompt formatting, response parsing, and error handling.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.llm_client import LLMClient


class TestLLMClientInitialization:
    """Tests for LLMClient initialization and configuration."""

    def test_client_initialization_with_custom_model(self) -> None:
        """Verify client initializes with custom model name."""
        client = LLMClient(model_name="custom-model")
        assert client.model_name == "custom-model"

    def test_client_uses_env_var_when_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify client uses OLLAMA_MODEL environment variable."""
        monkeypatch.setenv("OLLAMA_MODEL", "env-model")
        client = LLMClient()
        assert client.model_name == "env-model"

    def test_client_uses_default_model_when_no_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify client uses default model when no env var is set."""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        client = LLMClient()
        assert client.model_name == "qwen3.5:35b"

    def test_client_default_url(self) -> None:
        """Verify client uses correct default URL."""
        client = LLMClient()
        assert client.url == "http://localhost:11434/api/generate"

    def test_client_system_prompt_is_set(self) -> None:
        """Verify system prompt is properly initialized."""
        client = LLMClient()
        assert client.system_prompt is not None
        assert "Playwright" in client.system_prompt


class TestGenerateTestMethod:
    """Tests for the generate_test method."""

    def test_raises_error_on_empty_request(self) -> None:
        """Verify ValueError is raised for empty request."""
        client = LLMClient()
        with pytest.raises(ValueError) as exc_info:
            client.generate_test("")
        assert "empty" in str(exc_info.value).lower()

    @patch("src.llm_client.requests.post")
    def test_generate_test_calls_api_correctly(self, mock_post: MagicMock) -> None:
        """Verify API call is made with correct payload."""
        # Clear both CI and OLLAMA_MODEL so defaults are used
        with patch.dict(os.environ, {"CI": ""}):
            os.environ.pop("OLLAMA_MODEL", None)  # remove so default qwen3.5:35b is used
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "test code"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            client = LLMClient()
            _ = client.generate_test("test scenario")
            assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "qwen3.5:35b"
        assert "test scenario" in call_args[1]["json"]["prompt"]

    @patch("src.llm_client.requests.post")
    def test_generate_test_returns_extracted_code(self, mock_post: MagicMock) -> None:
        """Verify extracted code is returned."""
        with patch.dict(os.environ, {"CI": ""}):
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "```python\ntest code\n```"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            client = LLMClient()
            result = client.generate_test("test scenario")

            assert result == "test code"

    @patch("src.llm_client.requests.post")
    def test_generate_test_with_trailing_newline(self, mock_post: MagicMock) -> None:
        """Verify code with trailing newline is handled correctly."""
        with patch.dict(os.environ, {"CI": ""}):
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "```python\ntest code\n```"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            client = LLMClient()
            result = client.generate_test("test scenario")

            assert result == "test code"

    @patch("src.llm_client.requests.post")
    def test_generate_test_with_additional_context(self, mock_post: MagicMock) -> None:
        """Verify additional context is included in prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "test code"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = LLMClient()
        client.generate_test("test scenario", additional_context={"selector": "#my-button"})

        call_args = mock_post.call_args
        if os.getenv("CI", "") != "true":
            assert "#my-button" in call_args[1]["json"]["prompt"]

    @patch("src.llm_client.requests.post")
    def test_connection_error_handling(self, mock_post: MagicMock) -> None:
        """Verify RuntimeError is raised for connection failures."""
        with patch.dict(os.environ, {"CI": ""}):
            mock_post.side_effect = Exception("Connection failed")
            client = LLMClient()
            with pytest.raises(RuntimeError) as exc_info:
                client.generate_test("test scenario")
            assert "Ollama request failed: Connection failed" in str(exc_info.value)


class TestExtractCodeMethod:
    """Tests for the _extract_code method."""

    def test_extracts_code_with_markdown_fences(self) -> None:
        """Verify code is extracted from markdown fences."""
        client = LLMClient()
        input_text = "```python\ntest code\n```"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_extracts_code_with_language_specifier(self) -> None:
        """Verify code extraction handles language specifier."""
        client = LLMClient()
        input_text = "```python\ntest code\n```"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_extracts_code_without_language(self) -> None:
        """Verify extraction works without language specifier."""
        client = LLMClient()
        input_text = "```\ntest code\n```"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_returns_text_without_fences(self) -> None:
        """Verify raw text is returned as-is when no fences."""
        client = LLMClient()
        input_text = "raw code here"
        result = client._extract_code(input_text)
        assert result == "raw code here"

    def test_removes_surrounding_whitespace(self) -> None:
        """Verify surrounding whitespace is stripped."""
        client = LLMClient()
        input_text = "\n```python\ntest code\n```\n"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_handles_extra_content_around_code(self) -> None:
        """Verify content before/after code block is handled."""
        client = LLMClient()
        input_text = "Some explanation\n\n```python\ntest code\n```\nMore text"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_handles_empty_code_block(self) -> None:
        """Verify empty code blocks are handled."""
        client = LLMClient()
        input_text = "```\n```"
        result = client._extract_code(input_text)
        assert result == ""


class TestSystemPromptContent:
    """Tests for verifying system prompt content and quality."""

    def test_system_prompt_contains_playwright_import(self) -> None:
        """Verify system prompt instructs correct import."""
        client = LLMClient()
        assert "playwright" in client.system_prompt.lower()

    def test_system_prompt_includes_screenshot_instructions(self) -> None:
        """Verify system prompt includes screenshot instructions."""
        client = LLMClient()
        assert "screenshot" in client.system_prompt.lower()

    def test_system_prompt_uses_sync_api(self) -> None:
        """Verify system prompt specifies sync API usage (pytest-playwright standard)."""
        client = LLMClient()
        assert "sync_api" in client.system_prompt.lower()
        # async_playwright appears only in a "DO NOT use" instruction — not as an instruction to use it
        assert "do not use asyncio, async def, or async_playwright" in client.system_prompt.lower()

    def test_system_prompt_excludes_pytest_import(self) -> None:
        """Verify system prompt explicitly excludes pytest."""
        client = LLMClient()
        assert "pytest" in client.system_prompt.lower()
        # The prompt uses "Do NOT include `import pytest`"
        assert "do not" in client.system_prompt.lower() and "import pytest" in client.system_prompt.lower()


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @patch("src.llm_client.requests.post")
    def test_connection_error_message(self, mock_post: MagicMock) -> None:
        """Verify helpful error message for connection failures."""
        with patch.dict(os.environ, {"CI": ""}):
            mock_post.side_effect = Exception("Connection refused")
            client = LLMClient()
            with pytest.raises(RuntimeError) as exc_info:
                client.generate_test("test")
            assert "Ollama request failed: Connection refused" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
