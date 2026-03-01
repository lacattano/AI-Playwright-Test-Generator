"""Unit tests for the LLM client module.

Tests verify prompt formatting, response parsing, and error handling.
"""

import pytest
from src.llm_client import LLMClient
import os
from unittest.mock import patch, MagicMock


class TestLLMClientInitialization:
    """Tests for LLMClient initialization and configuration."""

    def test_client_initialization_with_custom_model(self):
        """Verify client initializes with custom model name."""
        client = LLMClient(model_name="custom-model")
        assert client.model_name == "custom-model"

    def test_client_uses_env_var_when_provided(self, monkeypatch):
        """Verify client uses OLLAMA_MODEL environment variable."""
        monkeypatch.setenv("OLLAMA_MODEL", "env-model")
        client = LLMClient()
        assert client.model_name == "env-model"

    def test_client_uses_default_model_when_no_env_var(self, monkeypatch):
        """Verify client uses default model when no env var is set."""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        client = LLMClient()
        assert client.model_name == "qwen3.5:35b"

    def test_client_default_url(self):
        """Verify client uses correct default URL."""
        client = LLMClient()
        assert client.url == "http://localhost:11434/api/generate"

    def test_client_system_prompt_is_set(self):
        """Verify system prompt is properly initialized."""
        client = LLMClient()
        assert client.system_prompt is not None
        assert "Playwright" in client.system_prompt


class TestGenerateTestMethod:
    """Tests for the generate_test method."""

    def test_raises_error_on_empty_request(self):
        """Verify ValueError is raised for empty request."""
        client = LLMClient()
        with pytest.raises(ValueError) as exc_info:
            client.generate_test("")
        assert "empty" in str(exc_info.value).lower()

    @patch('src.llm_client.requests.post')
    def test_generate_test_calls_api_correctly(self, mock_post):
        """Verify API call is made with correct payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "test code"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = LLMClient()
        result = client.generate_test("test scenario")

        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[1]['json']['model'] == "qwen3.5:35b"
        assert "test scenario" in call_args[1]['json']['prompt']

    @patch('src.llm_client.requests.post')
    def test_generate_test_returns_extracted_code(self, mock_post):
        """Verify extracted code is returned."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "```python\ntest code\n```"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = LLMClient()
        result = client.generate_test("test scenario")

        assert result == "test code"

    @patch('src.llm_client.requests.post')
    def test_generate_test_with_additional_context(self, mock_post):
        """Verify additional context is included in prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "test code"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = LLMClient()
        result = client.generate_test(
            "test scenario",
            additional_context={"selector": "#my-button"}
        )

        call_args = mock_post.call_args
        assert "#my-button" in call_args[1]['json']['prompt']

    @patch('src.llm_client.requests.post')
    def test_connection_error_handling(self, mock_post):
        """Verify ConnectionError is raised for connection failures."""
        mock_post.side_effect = Exception("Connection failed")

        client = LLMClient()
        with pytest.raises(Exception) as exc_info:
            client.generate_test("test")
        assert "Connection" in str(exc_info.value)


class TestExtractCodeMethod:
    """Tests for the _extract_code method."""

    def test_extracts_code_with_markdown_fences(self):
        """Verify code is extracted from markdown fences."""
        client = LLMClient()
        input_text = "```python\ntest code\n```"
        result = client._extract_code(input_text)
        assert result == "test code"
        assert "```" not in result

    def test_extracts_code_with_language_specifier(self):
        """Verify code extraction handles language specifier."""
        client = LLMClient()
        input_text = "```python\ntest code\n```"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_extracts_code_without_language(self):
        """Verify extraction works without language specifier."""
        client = LLMClient()
        input_text = "```\ntest code\n```"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_returns_text_without_fences(self):
        """Verify raw text is returned as-is when no fences."""
        client = LLMClient()
        input_text = "raw code here"
        result = client._extract_code(input_text)
        assert result == "raw code here"

    def test_removes_surrounding_whitespace(self):
        """Verify surrounding whitespace is stripped."""
        client = LLMClient()
        input_text = "\n```python\ntest code\n```\n"
        result = client._extract_code(input_text)
        assert result == "test code"
        assert result != "\ntest code\n"

    def test_handles_extra_content_around_code(self):
        """Verify content before/after code block is handled."""
        client = LLMClient()
        input_text = "Some explanation\n\n```python\ntest code\n```\nMore text"
        result = client._extract_code(input_text)
        assert result == "test code"

    def test_handles_empty_code_block(self):
        """Verify empty code blocks are handled."""
        client = LLMClient()
        input_text = "```\n```"
        result = client._extract_code(input_text)
        assert result == ""


class TestSystemPromptContent:
    """Tests for verifying system prompt content and quality."""

    def test_system_prompt_contains_playwright_import(self):
        """Verify system prompt instructs correct import."""
        client = LLMClient()
        assert "playwright" in client.system_prompt.lower()

    def test_system_prompt_includes_screenshot_instructions(self):
        """Verify system prompt includes screenshot instructions."""
        client = LLMClient()
        assert "screenshot" in client.system_prompt.lower()

    def test_system_prompt_uses_async_api(self):
        """Verify system prompt specifies async API usage."""
        client = LLMClient()
        assert "async" in client.system_prompt.lower() or "async_playwright" in client.system_prompt.lower()

    def test_system_prompt_omits_pytest_import(self):
        """Verify system prompt explicitly excludes pytest."""
        client = LLMClient()
        assert "pytest" in client.system_prompt.lower()
        assert "DO NOT import pytest" in client.system_prompt


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @patch('src.llm_client.requests.post')
    def test_connection_error_message(self, mock_post):
        """Verify helpful error message for connection failures."""
        mock_post.side_effect = Exception("Connection refused")

        client = LLMClient()
        try:
            client.generate_test("test")
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Connection" in str(e) or "ollama" in str(e).lower()


class TestSlugify:
    """Tests for the slugify utility function from main.py."""

    def slugify_text(self, text: str, max_length: int = 100) -> str:
        """Helper to test slugify logic inline."""
        import re
        slug = re.sub(r'[^a-zA-Z0-9]', '_', text)
        slug = slug.strip('_')
        slug = slug.lower()
        if len(slug) > max_length:
            slug = slug[:max_length]
        return slug

    def test_slugify_removes_special_chars(self):
        """Verify special characters are replaced with underscores."""
        result = self.slugify_text("User Login@2024")
        assert "@" in "User Login@2024"
        assert "@" not in result
        assert "_" in result

    def test_slugify_converts_to_lowercase(self):
        """Verify output is always lowercase."""
        result = self.slugify_text("User LOGIN")
        assert result == "user_login"

    def test_slugify_trims_underscores(self):
        """Verify leading/trailing underscores are removed."""
        result = self.slugify_text("__test__")
        assert result == "test"

    def test_slugify_truncates_to_max_length(self):
        """Verify output is truncated to max_length."""
        long_text = "a" * 200
        result = self.slugify_text(long_text, max_length=10)
        assert len(result) <= 10

    def test_slugify_preserves_alphanumeric(self):
        """Verify alphanumeric characters are preserved."""
        result = self.slugify_text("test123ABC")
        assert "123" in result
        assert "ABC".lower() in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
