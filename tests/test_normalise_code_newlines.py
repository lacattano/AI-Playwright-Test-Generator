"""Tests for normalise_code_newlines in src/file_utils.py

Covers the B-002 bug: LLM output occasionally has all imports on one
line, producing a SyntaxError when the file is executed.
"""

from src.file_utils import normalise_code_newlines


class TestNormaliseCodeNewlines:
    """Tests for normalise_code_newlines."""

    def test_restores_newline_between_bare_imports(self) -> None:
        """Two bare imports run together get a newline inserted."""
        result = normalise_code_newlines("import osimport re")
        assert result == "import os\nimport re"

    def test_restores_newline_between_from_imports(self) -> None:
        """from-import followed by bare import gets newline restored."""
        result = normalise_code_newlines("from pathlib import Pathimport os")
        assert result == "from pathlib import Path\nimport os"

    def test_restores_newline_multiple_collapsed_imports(self) -> None:
        """Full collapsed import block is fully restored."""
        collapsed = "from playwright.sync_api import Pageimport pytestimport os"
        result = normalise_code_newlines(collapsed)
        assert "from playwright.sync_api import Page\n" in result
        assert "import pytest\n" in result
        assert "import os" in result

    def test_leaves_correct_newlines_unchanged(self) -> None:
        """Code that already has newlines is not modified."""
        code = "import os\nimport re\nfrom pathlib import Path\n"
        result = normalise_code_newlines(code)
        assert result == code

    def test_handles_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert normalise_code_newlines("") == ""

    def test_does_not_affect_import_inside_string(self) -> None:
        """The word 'import' inside a string literal is not split."""
        code = 'x = "do not import this"\nimport os'
        result = normalise_code_newlines(code)
        # The string literal must be untouched
        assert '"do not import this"' in result

    def test_does_not_double_newline_when_already_present(self) -> None:
        """A newline already before import does not become a blank line."""
        code = "import os\nimport re"
        result = normalise_code_newlines(code)
        assert "\n\n" not in result

    def test_real_world_collapsed_output(self) -> None:
        """Simulate the exact B-002 symptom from a real LLM response."""
        collapsed = (
            "from playwright.sync_api import sync_playwright, Page, expect"
            "import pytest"
            "import os"
            "from pathlib import Path"
        )
        result = normalise_code_newlines(collapsed)
        lines = result.splitlines()
        # Every logical import statement should be on its own line
        assert any("from playwright" in line for line in lines)
        assert any(line.strip() == "import pytest" for line in lines)
        assert any(line.strip() == "import os" for line in lines)
        assert any("from pathlib" in line for line in lines)
