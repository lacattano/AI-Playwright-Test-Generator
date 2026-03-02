import os
import re

import requests


class LLMClient:
    def __init__(self, model_name: str | None = None):
        """
        Initialize the LLM Client with the specified model.
        Falls back to OLLAMA_MODEL environment variable or default.
        """
        self.url = "http://localhost:11434/api/generate"
        self._model = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:35b")
        self.user_prompt: str | None = None
        self.response: dict | None = None
        self.system_prompt: str = """You are an expert Playwright testing engineer.
        Your task is to generate clean, modern, and robust Playwright (Python) test code with screenshot capture for test evidence.
        Follow these rules:
        1. Import from `playwright.async_api import async_playwright, Page, expect`.
        2. Include comments explaining the steps.
        3. Return ONLY the code block inside triple backticks. Do not add explanations.
        4. Handle waits implicitly where possible, but use explicit waits for dynamic content.
        5. Use meaningful selector strategies (data-testid, CSS, XPath, get_by_role, get_by_label, etc.).
        6. The test should cover the specific scenario requested.
        7. IMPORTANT: Do NOT include `import pytest` - the test will be run directly as a Python script.
        8. IMPORTANT: Use async/await with async_playwright for the test execution.
        9. IMPORTANT: Test against URL http://localhost:8080 for the mock insurance site.
        10. The generated test must be runnable as a standalone script with: python test_filename.py.
        11. CAPTURE SCREENSHOTS for test evidence:
            - Take screenshot on test entry: screenshots/test_entry_YYYYMMDD_HHMMSS.png
            - Take screenshot after key interactions (form fills, button clicks): screenshots/step_description_YYYYMMDD_HHMMSS.png
            - Take screenshot on success condition is met: screenshots/test_passed_YYYYMMDD_HHMMSS.png
            - Playwright automatically captures screenshot on assertion failure in the console.
        12. Use try/except to capture screenshot on failure. The test must save screenshots to a 'screenshots/' subdirectory."""

    @property
    def model_name(self) -> str:
        """Return the current model name being used."""
        return self._model

    def generate_test(
        self, user_request: str, additional_context: dict | None = None
    ) -> str:
        """
        Generate a test script based on a user request description.
        user_request: A string describing the test scenario.
        additional_context: A dictionary containing additional context (e.g., selectors, page URL).
        """
        self.user_prompt = f"Scenario: {user_request}"
        if additional_context:
            self.user_prompt += f"\nAdditional Context: {additional_context}"

        if not user_request:
            raise ValueError("User request cannot be empty.")

        payload = {
            "model": self.model_name,
            "prompt": self.user_prompt,
            "system": self.system_prompt,
            "stream": False,
        }
        try:
            # Configurable timeout (default 60s, can be overridden via OLLAMA_TIMEOUT env var)
            timeout = int(os.getenv("OLLAMA_TIMEOUT", "60"))
            response = requests.post(self.url, json=payload, timeout=timeout)
            response.raise_for_status()
            self.response = response.json()
            raw = self.response.get("response") if self.response else ""
            full_response: str = raw if isinstance(raw, str) else ""
            return self._extract_code(full_response)
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                "Could not connect to Ollama. Ensure it is running on port 11434."
            ) from e
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return ""
        except Exception as e:
            raise RuntimeError(f"Error generating code: {e}") from e

    def _extract_code(self, text: str) -> str:
        """
        Extract the code block enclosed in triple backticks.
        Returns code content stripped of surrounding whitespace.
        """
        pattern = r"```(?:python)?\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            # Strip trailing whitespace (including newline) before closing fences
            result: str = match.group(1).rstrip()
            return result
        # Return empty string if no match found to ensure consistent return type
        return ""
