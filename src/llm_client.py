"""
LLM Client for generating Playwright tests from user stories.

This module provides a high-level interface for interacting with LLM providers
to generate test scripts based on acceptance criteria. It supports multiple backends:
- Ollama (local)
- LM Studio (local, OpenAI-compatible)
- OpenAI (cloud)

The client handles conversation management, error handling, and token usage tracking.
"""

import re
from typing import Any

from src.llm_providers import ChatMessage, create_provider_from_env, get_provider


class LLMClient:
    """Client for interacting with LLM providers to generate tests.

    This class manages the conversation state and provides methods for
    generating test code from user stories/acceptance criteria.

    Attributes:
        system_instruction: The system prompt used for all conversations.
        _conversation_history: List of ChatMessage objects representing the current session.
        _provider: The LLM provider instance (OllamaProvider, LMStudioProvider, or OpenAIProvider).
        _model: The model name to use for completions.
    """

    DEFAULT_SYSTEM_INSTRUCTION = """You are an expert QA engineer and Python developer specializing in Playwright testing. Your task is to convert user stories with acceptance criteria into production-ready Playwright test scripts using pytest and the sync API.

CRITICAL REQUIREMENTS:
1. Generate ONE test function per criterion (e.g., test_01_shows_homepage, test_02_allows_login)
2. Use pytest sync format ONLY - do not use asyncio, async def, or async_playwright
3. Import playwright.sync_api fixtures properly and include `from playwright.sync_api import Page, expect` at the top of every generated file.
4. Use pytest-playwright fixture style: `page` should be passed as the test argument. Do NOT use `sync_playwright()` or manual browser launch code.
5. Use valid Playwright Python sync APIs only. For example, use `page.goto(url)`, `expect(page).to_have_url(...)`, `expect(page).to_have_title(...)`, or `assert page.title() == ...`.
6. Prefer exact assertions for known URL and title values. Only use `re.compile(...)` when the expected string may vary, and if you use regex, include `import re` at the top of the file.
7. For root-domain navigation like `https://example.com`, assert the canonical trailing-slash URL: `expect(page).to_have_url('https://example.com/')`, or use a regex with an optional trailing slash if necessary.
8. Do NOT use `expect(page.title())`, `expect(page.url())`, or any `expect(...)` call on a raw string return value. Use `page.title()` with a plain Python `assert` or `expect(page).to_have_title(...)` instead.
9. Avoid custom pytest markers or screenshot helpers such as `@pytest.mark.screenshot` and `from playwright.sync_api import screenshot`. Use standard assertions only.
8. Do NOT use `expect(page).to_be_connected()`, `expect(page).to_have_url_containing(...)`, `expect(page).to_have_title_containing(...)`, or any invalid Playwright assertion method.
9. Do NOT use `page.wait_for_load_state(...).status` or any pattern that assumes `wait_for_load_state` returns a response.
9. Each test must be independent and runnable standalone.
10. Include clear, descriptive test names that match the criterion number.
11. Add docstrings explaining what each test verifies.
12. Take screenshots on test failures and key interactions for evidence.

OUTPUT FORMAT:
- Return ONLY valid Python code
- Do NOT include `import pytest` in the generated code
- No markdown formatting (no ```python blocks)
- No explanations or commentary
- Just the raw test code"""

    def __init__(
        self,
        provider_name: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize the LLM client.

        Args:
            provider_name: Name of the LLM provider ('ollama', 'lm-studio', or 'openai').
                          If None, uses LLM_PROVIDER env var (default: 'ollama').
            model: Optional default model name. Falls back to provider-specific defaults.
            base_url: Optional provider base URL.
            api_key: Optional API key for OpenAI provider.
        """
        if provider_name is not None:
            self._provider = get_provider(provider_name, base_url=base_url, api_key=api_key)
        else:
            self._provider = create_provider_from_env()

        self._model = model or self._get_default_model()
        self.system_instruction = self.DEFAULT_SYSTEM_INSTRUCTION
        self._conversation_history: list[ChatMessage] = []

    def _get_default_model(self) -> str:
        """Get the default model based on provider."""
        import os

        if self._provider.provider_name == "ollama":
            return os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        elif self._provider.provider_name == "lm-studio":
            return os.environ.get("LM_STUDIO_MODEL", "lmstudio-community/Qwen2.5-7B-Instruct-GGUF")
        else:  # openai
            return os.environ.get("OPENAI_MODEL", "gpt-4o")

    def reset_conversation(
        self,
        system_instruction: str | None = None,
        *,
        system_prompt: str | None = None,
    ) -> None:
        """Reset the conversation history, keeping only the system instruction."""
        system_text = system_prompt or system_instruction or self.system_instruction
        self._conversation_history = [ChatMessage(role="system", content=system_text)]

    @property
    def provider_name(self) -> str:
        """Returns the name of the current LLM provider."""
        return self._provider.provider_name

    @property
    def model(self) -> str:
        """Returns the current model being used."""
        return self._model

    @property
    def base_url(self) -> str:
        """Returns the configured provider base URL."""
        return self._provider.base_url

    def generate_tests(self, acceptance_criteria: list[str], timeout: int = 300) -> dict[str, Any]:
        """Generate Playwright tests from a list of acceptance criteria.

        Args:
            acceptance_criteria: List of strings, each describing an acceptance criterion.
            timeout: Request timeout in seconds.

        Returns:
            Dictionary containing:
                - 'test_code': The generated Python test code (string)
                - 'model_used': The model name that was used
                - 'provider_used': The provider name
                - 'tokens_used': Token usage info if available

        Raises:
            TimeoutError: If the request exceeds the timeout.
            ConnectionError: If the provider is unreachable.
            ValueError: If acceptance_criteria is empty or malformed.
        """
        if not acceptance_criteria:
            raise ValueError("acceptance_criteria cannot be empty")

        # Build prompt with numbered criteria (LLM follows structure better)
        criteria_text = "\n".join([f"{i + 1}. {criterion}" for i, criterion in enumerate(acceptance_criteria)])
        total_count = len(acceptance_criteria)

        user_prompt = f"""You are an expert QA engineer creating Playwright tests. Convert these acceptance criteria into pytest sync test functions.

ACCEPTANCE CRITERIA ({total_count} total):
{criteria_text}

Total: {total_count} criteria

INSTRUCTIONS:
- Generate EXACTLY ONE test function per criterion (e.g., test_01_criterion, test_02_criterion)
- DO NOT use async def — use pytest sync format only
- DO NOT skip, combine, or omit any criteria
- Each test must be independent and runnable standalone

CRITICAL: All {total_count} criteria must have tests. DO NOT skip the last few."""

        # Add user message to conversation
        self._conversation_history.append(ChatMessage(role="user", content=user_prompt))

        try:
            completion = self._provider.complete(
                messages=self._conversation_history, model=self._model, timeout=timeout
            )

            # Store assistant response in history
            self._conversation_history.append(ChatMessage(role="assistant", content=completion.content))

            return {
                "test_code": completion.content.strip(),
                "model_used": completion.model,
                "provider_used": self._provider.provider_name,
                "tokens_used": completion.usage or {},
            }

        except Exception as e:
            # Clean up conversation on error
            self._conversation_history.pop()  # Remove user message we just added
            raise RuntimeError(f"Failed to generate tests: {str(e)}") from e

    def generate_test(self, prompt: str, timeout: int = 300, system_prompt: str | None = None) -> str:
        """Generate raw test code from a prompt string.

        Args:
            prompt: The user message or page context prompt.
            timeout: Request timeout in seconds.
            system_prompt: Optional system prompt text to send as a system role.

        Returns:
            The cleaned raw text response from the model.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        self.reset_conversation(system_prompt=system_prompt)
        self._conversation_history.append(ChatMessage(role="user", content=prompt))

        try:
            completion = self._provider.complete(
                messages=self._conversation_history, model=self._model, timeout=timeout
            )
            self._conversation_history.append(ChatMessage(role="assistant", content=completion.content))
            cleaned = self._extract_code(completion.content)
            return self.normalise_code_newlines(cleaned)
        except Exception as e:
            self._conversation_history.pop()
            raise RuntimeError(f"Failed to generate tests: {str(e)}") from e

    def get_conversation_summary(self) -> dict[str, Any]:
        """Get a summary of the current conversation state.

        Returns:
            Dictionary with conversation metadata.
        """
        return {
            "provider": self._provider.provider_name,
            "model": self._model,
            "message_count": len(self._conversation_history),
            "system_instruction_length": len(self.system_instruction),
        }

    def normalise_code_newlines(self, code: str) -> str:
        """Normalizes line endings in generated test code.

        Simple cleanup: remove extra whitespace and ensure proper line endings.
        Do NOT try to add newlines aggressively as this can break multi-line statements.

        Args:
            code: The raw generated code.

        Returns:
            Code with basic cleanup applied.
        """
        if not code or not code.strip():
            return code.strip()

        # Only do minimal cleanup: normalize line endings and remove trailing spaces
        lines = code.split("\n")
        cleaned_lines = [line.rstrip() for line in lines]
        # Remove empty lines at start and end
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()

        return "\n".join(cleaned_lines)

    def _extract_code(self, raw_text: str) -> str:
        """Clean LLM completion text by extracting only valid Python code."""
        if not raw_text:
            return ""

        # Remove any LM Studio channel markers or other stray delimiters
        cleaned = re.sub(r"<channel\|>+", "", raw_text)

        # Extract fenced code blocks if present
        fence_match = re.search(r"```(?:python)?\n(.+?)```", cleaned, re.S)
        if fence_match:
            return fence_match.group(1).strip()

        # Handle empty fenced code blocks explicitly
        if re.match(r"^```(?:python)?\s*```$", cleaned.strip(), re.S):
            return ""

        # If the model echo includes the prompt or extra prose before the code,
        # keep everything starting from the first likely code entry point.
        import_match = re.search(r"(?:from\s+playwright\.sync_api\s+import|import\s+pytest)", cleaned)
        if import_match:
            return cleaned[import_match.start() :].strip()

        def_match = re.search(r"def\s+test_", cleaned)
        if def_match:
            return cleaned[def_match.start() :].strip()

        decorator_match = re.search(r"@pytest\.mark", cleaned)
        if decorator_match:
            return cleaned[decorator_match.start() :].strip()

        return cleaned.strip()


def create_llm_client(provider_name: str | None = None, model: str | None = None) -> LLMClient:
    """Factory function to create an LLM client instance.

    Args:
        provider_name: Name of the LLM provider ('ollama', 'lm-studio', or 'openai').
                      If None, uses LLM_PROVIDER env var (default: 'ollama').
        model: Optional default model name. Falls back to provider-specific defaults.

    Returns:
        An instantiated LLMClient configured for the specified provider and model.
    """
    return LLMClient(provider_name=provider_name, model=model)
