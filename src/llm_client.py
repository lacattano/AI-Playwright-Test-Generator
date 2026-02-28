import os
import requests
import re
from typing import Optional

class LLMClient:
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the LLM Client with the specified model.
        Falls back to OLLAMA_MODEL environment variable or default.
        """
        self.url = "http://localhost:11434/api/generate"
        self._model = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:35b")
        self.user_prompt: Optional[str] = None
        self.response: Optional[dict] = None
        self.system_prompt: str = """You are an expert Playwright testing engineer.
        Your task is to generate clean, modern, and robust Playwright (Python) test code using pytest.
        Follow these rules:
        1. Use the pytest-playwright `page` fixture (sync API, not async).
        2. Import from `playwright.sync_api import Page, expect`.
        3. Include comments explaining the steps.
        4. Return ONLY the code block inside triple backticks. Do not add explanations.
        5. Handle waits implicitly where possible, but use explicit waits for dynamic content.
        6. Use meaningful selector strategies (data-testid, CSS, XPath, get_by_role, get_by_label, etc.).
        7. The test should cover the specific scenario requested.
        8. IMPORTANT: Do NOT use setup_method with self.page - set the timeout directly in the test function using page.set_default_timeout().
        9. IMPORTANT: Do NOT define attributes like self.page or self.locator in a class - just use page fixture directly in test functions.
        10. IMPORTANT: Use the page fixture parameter in test methods, not self.page."""

    @property
    def model_name(self) -> str:
        """Return the current model name being used."""
        return self._model

    def generate_test(self, user_request: str, additional_context: dict | None = None) -> str:
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
            "stream": False
        }
        try:
            # Configurable timeout (default 60s, can be overridden via OLLAMA_TIMEOUT env var)
            timeout = int(os.getenv("OLLAMA_TIMEOUT", "60"))
            response = requests.post(self.url, json=payload, timeout=timeout)
            response.raise_for_status()
            self.response = response.json()
            full_response: str = self.response.get("response", "") if self.response else ""
            return self._extract_code(full_response)
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Could not connect to Ollama. Ensure it is running on port 11434.")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return ""
        except Exception as e:
            raise Exception(f"Error generating code: {e}")

    def _extract_code(self, text: str) -> str:
        """
        Extract the code block enclosed in triple backticks.
        """
        pattern = r'```(?:python)?\n(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        return text.strip()

