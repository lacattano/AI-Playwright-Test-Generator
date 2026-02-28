"""Unit tests for the test generator module."""
import os
from unittest.mock import patch

import pytest

# Ensure the src directory is in the Python path
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm_client import LLMClient
from test_generator import TestGenerator


class TestTestGenerator:
    """Tests for the TestGenerator class."""

    def test_init_creates_output_dir(self, tmp_path):
        """Test that __init__ creates the output directory if it doesn't exist."""
        output_dir = str(tmp_path / "output")
        generator = TestGenerator(output_dir=output_dir)
        assert os.path.exists(output_dir)
        assert os.path.isdir(output_dir)

    def test_init_uses_default_output_dir(self, tmp_path, monkeypatch):
        """Test that __init__ uses 'generated_tests' as default output directory."""
        monkeypatch.chdir(tmp_path)
        generator = TestGenerator()
        assert generator.output_dir == "generated_tests"

    def test_generate_and_save_calls_llm_client(self):
        """Test that generate_and_save calls the LLM client."""
        generator = TestGenerator()
        with patch.object(
            generator.client, "generate_test", return_value="print('hello')"
        ) as mock_generate:
            generator.generate_and_save("test feature")
            mock_generate.assert_called_once_with("test feature")


class TestLLMClient:
    """Tests for the LLMClient class."""

    def test_init_uses_env_var_for_model(self):
        """Test that __init__ uses OLLAMA_MODEL env var when provided."""
        import os

        os.environ["OLLAMA_MODEL"] = "env-model"
        client = LLMClient()
        assert client.model_name == "env-model"
        del os.environ["OLLAMA_MODEL"]

    def test_init_defaults_to_qwen35_35b(self):
        """Test that __init__ defaults to qwen3.5:35b when no model specified."""
        client = LLMClient()
        assert client.model_name == "qwen3.5:35b"

    def test_init_accepts_custom_model(self):
        """Test that __init__ accepts custom model name."""
        client = LLMClient(model_name="custom-model")
        assert client.model_name == "custom-model"
