"""Tests for generated-package execution service."""

from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

from src.pipeline_run_service import PipelineRunService
from src.pytest_output_parser import RunResult, TestResult


def test_run_saved_test_executes_pytest_module_and_parses_output() -> None:
    service = PipelineRunService()
    stdout = """
generated_tests/test_demo.py::test_checkout PASSED [100%]
============================== 1 passed in 1.20s ==============================
"""

    with patch("src.pipeline_run_service.subprocess.run") as mock_run:
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
        result = service.run_saved_test("generated_tests/test_demo.py", cwd=".")

    assert result.command[:3] == ["python", "-m", "pytest"] or result.command[1:3] == ["-m", "pytest"]
    assert result.run_result.passed == 1
    assert "test_checkout PASSED" in result.display_output
    assert result.return_code == 0


def test_run_saved_test_uses_failed_only_rerun_when_requested() -> None:
    service = PipelineRunService()
    previous_run = RunResult(
        results=[
            TestResult(
                name="test_checkout[chromium]",
                status="failed",
                duration=0.0,
                error_message="boom",
                file_path="generated_tests/test_demo.py",
            )
        ]
    )

    with patch("src.pipeline_run_service.subprocess.run") as mock_run:
        mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        result = service.run_saved_test(
            "generated_tests/test_demo.py",
            rerun_failed_only=True,
            previous_run=previous_run,
            cwd=".",
        )

    assert "generated_tests/test_demo.py::test_checkout[chromium]" in result.command
