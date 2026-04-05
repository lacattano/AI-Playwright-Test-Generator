"""
Test Generator module - generates Playwright test scripts.
"""

import os
from datetime import datetime

from src.code_validator import (
    validate_generated_locator_quality,
    validate_python_syntax,
    validate_test_function,
)
from src.llm_client import LLMClient
from src.page_context_scraper import PageContext, scrape_page_context


class TestGenerator:
    def __init__(
        self,
        model_name: str | None = None,
        output_dir: str = "generated_tests",
        page_url: str | None = None,
        provider_name: str | None = None,
        provider_base_url: str | None = None,
        provider_api_key: str | None = None,
    ) -> None:
        """
        Initialize the generator.
        model_name: Model to use (defaults to env model or provider-specific default).
        output_dir: Where to save the generated test files.
        page_url: Optional URL to scrape for page context.
        provider_name: LLM provider to use ('ollama', 'lm-studio', or 'openai').
        provider_base_url: Optional service URL for the provider.
        provider_api_key: Optional API key for OpenAI.
        """
        self.client = LLMClient(
            provider_name=provider_name,
            model=model_name,
            base_url=provider_base_url,
            api_key=provider_api_key,
        )
        self.output_dir = output_dir
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:35b")
        self.page_url = page_url
        self.generated_files: list[str] = []

        # Create output directory if it doesn't exist and validate it's writable
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """Create output directory if needed and validate write permissions."""
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                print(f"📁 Created output directory: {self.output_dir}")

            # Test write permissions
            test_file = os.path.join(self.output_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)

        except PermissionError as e:
            raise PermissionError(f"Write permission denied for output directory: {self.output_dir}") from e
        except OSError as e:
            raise OSError(f"Failed to create/access output directory {self.output_dir}: {e}") from e

    def generate_and_save(
        self,
        user_request: str,
        page_context: PageContext | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        1. Scrapes page context if page_url is provided.
        2. Injects page context into the prompt if scraping succeeds.
        3. Generates code using the AI.
        4. Saves it to a file named based on the timestamp.
        5. Returns the filename.
        """
        try:
            # Step 1: Scrape page context if URL is provided
            if self.page_url:
                print(f"Scraping page context from: {self.page_url}")
                page_context, scrape_error = scrape_page_context(self.page_url)

                if page_context:
                    print(f"Successfully scraped {page_context.element_count()} interactive elements")
                    print(f"   Page title: {page_context.page_title}")
                    if page_context.h1_text:
                        print(f"   H1: {page_context.h1_text}")
                elif scrape_error:
                    print(f"Warning: Failed to scrape page: {scrape_error}")
                    print("   Continuing without page context...")
                    page_context = None

            # Step 2: Inject page context into user request if available
            if page_context:
                prompt_with_context = self._build_context_injected_prompt(user_request, page_context)
            else:
                prompt_with_context = user_request

            # Step 3: Contact AI model
            print("Contacting AI model...")
            code = self.client.generate_test(
                prompt_with_context,
                system_prompt=system_prompt,
            )

            if not code.strip():
                raise Exception("The AI returned empty code.")

            # Clean the code of leading/trailing whitespace and validate it.
            code = code.strip()
            code = self.client.normalise_code_newlines(code)

            syntax_error = validate_python_syntax(code)
            if syntax_error:
                raise ValueError(f"Generated code failed syntax validation: {syntax_error}")

            test_error = validate_test_function(code)
            if test_error:
                raise ValueError(f"Generated code failed test function validation: {test_error}")

            locator_error = validate_generated_locator_quality(code)
            if locator_error:
                raise ValueError(f"Generated code failed locator quality validation: {locator_error}")

            # Generate a filename based on the request (slugified) or timestamp
            # Using timestamp for uniqueness
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            slugified_request = "".join(c if c.isalnum() or c == "_" else "_" for c in user_request)[:30]
            safe_filename = f"test_{timestamp}_{slugified_request}.py"

            file_path = os.path.join(self.output_dir, safe_filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            print(f"Test generated and saved to: {os.path.abspath(file_path)}")
            print(f"Run with: cd {self.output_dir} && python {safe_filename}")
            print("Screenshots will be captured to 'screenshots/' subdirectory for test evidence")
            print("   - Test entry, step actions, success, and failure conditions")
            return file_path

        except Exception as e:
            print(f"Error during generation: {e}")
            raise

    def _build_context_injected_prompt(self, user_request: str, page_context: PageContext) -> str:
        """
        Build a prompt that includes page context for more precise test generation.

        Args:
            user_request: The original user story/request
            page_context: The scraped page context with interactive elements

        Returns:
            A prompt with page context injected for the LLM
        """
        return (
            "IMPORTANT: Use the following page context to generate precise Playwright locators.\n"
            "Only use the locators listed in the PAGE CONTEXT section. Do not invent your own selectors.\n\n"
            f"=== PAGE CONTEXT ===\n{page_context.to_prompt_block()}\n\n"
            f"=== USER STORY/REQUEST ===\n{user_request}"
        )
