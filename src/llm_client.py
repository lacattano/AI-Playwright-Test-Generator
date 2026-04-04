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

from src.llm_providers import ChatMessage, create_provider_from_env


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
2. Use pytest sync format ONLY - DO NOT use async def or asyncio
3. Import playwright.sync_api fixtures properly
4. Each test must be independent and runnable standalone
5. Include clear, descriptive test names that match the criterion number
6. Add docstrings explaining what each test verifies

OUTPUT FORMAT:
- Return ONLY valid Python code
- No markdown formatting (no ```python blocks)
- No explanations or commentary
- Just the raw test code"""

    def __init__(self, provider_name: str | None = None, model: str | None = None):
        """Initialize the LLM client.

        Args:
            provider_name: Name of the LLM provider ('ollama', 'lm-studio', or 'openai').
                          If None, uses LLM_PROVIDER env var (default: 'ollama').
            model: Optional default model name. Falls back to provider-specific defaults.
        """
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

    def reset_conversation(self) -> None:
        """Reset the conversation history, keeping only the system instruction."""
        self._conversation_history = [ChatMessage(role="system", content=self.system_instruction)]

    @property
    def provider_name(self) -> str:
        """Returns the name of the current LLM provider."""
        return self._provider.provider_name

    @property
    def model(self) -> str:
        """Returns the current model being used."""
        return self._model

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
            raise type(e)(f"Failed to generate tests: {str(e)}") from e

    def generate_test(self, prompt: str, timeout: int = 300) -> str:
        """Generate raw test code from a prompt string."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        self._conversation_history.append(ChatMessage(role="user", content=prompt))

        try:
            completion = self._provider.complete(
                messages=self._conversation_history, model=self._model, timeout=timeout
            )
            self._conversation_history.append(ChatMessage(role="assistant", content=completion.content))
            return completion.content.strip()
        except Exception as e:
            self._conversation_history.pop()
            raise type(e)(f"Failed to generate tests: {str(e)}") from e

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

        This fixes a common LLM bug where newlines are stripped from import statements,
        causing syntax errors like `import osimport sys`.

        Args:
            code: The raw generated code that may have missing newlines.

        Returns:
            Code with proper newline placement after keywords and at statement boundaries.
        """
        # Pattern 1: Fix "keywordword" patterns (e.g., "importos", "frommodule")
        keyword_patterns = [
            r"(?<!\n)import\s+(\w+)",
            r"(?<!\n)from\s+(\S+)\s+import",
            r"(?<!\n)def\s+\w+",
            r"(?<!\n)class\s+\w+",
            r"(?<!\n)if\s+",
            r"(?<!\n)else:",
            r"(?<!\n)elif\s+",
            r"(?<!\n)for\s+",
            r"(?<!\n)while\s+",
        ]

        for pattern in keyword_patterns:
            code = re.sub(pattern, lambda m: "\n" + m.group(0), code)

        # Pattern 2: Ensure each function/class definition starts on new line
        code = re.sub(r"(?<!\n)\ndef ", "\ndef ", code)
        code = re.sub(r"(?<!\n)\nclass ", "\nclass ", code)

        return code.strip()


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
