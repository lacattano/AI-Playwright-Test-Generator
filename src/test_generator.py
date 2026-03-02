"""
Test Generator module - generates Playwright test scripts.
"""

import os
from datetime import datetime

from src.llm_client import LLMClient


class TestGenerator:
    def __init__(
        self, model_name: str | None = None, output_dir: str = "generated_tests"
    ) -> None:
        """
        Initialize the generator.
        model_name: Ollama model to use (defaults to OLLAMA_MODEL env var or 'qwen3.5:35b' for generation quality).
        output_dir: Where to save the generated test files.
        """
        self.client = LLMClient(model_name=model_name)
        self.output_dir = output_dir
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:35b")

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
            raise PermissionError(
                f"Write permission denied for output directory: {self.output_dir}"
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to create/access output directory {self.output_dir}: {e}"
            )

    def generate_and_save(self, user_request: str) -> str:
        """
        1. Generates code using the AI.
        2. Saves it to a file named based on the timestamp.
        3. Returns the filename.
        """
        try:
            print("⏳ Contacting AI model...")
            code = self.client.generate_test(user_request)

            if not code.strip():
                raise Exception("The AI returned empty code.")

            # Clean the code of leading/trailing whitespace just in case
            code = code.strip()

            # Generate a filename based on the request (slugified) or timestamp
            # Using timestamp for uniqueness
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            slugified_request = "".join(
                c if c.isalnum() or c == "_" else "_" for c in user_request
            )[:30]
            safe_filename = f"test_{timestamp}_{slugified_request}.py"

            file_path = os.path.join(self.output_dir, safe_filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            print(f"✅ Test generated and saved to: {os.path.abspath(file_path)}")
            print(f"📖 Run with: cd {self.output_dir} && python {safe_filename}")
            print(
                "📸 Screenshots will be captured to 'screenshots/' subdirectory for test evidence"
            )
            print("   - Test entry, step actions, success, and failure conditions")
            return file_path

        except Exception as e:
            print(f"❌ Error during generation: {e}")
            raise
