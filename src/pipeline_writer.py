"""Write intelligent-pipeline outputs as a structured artifact package."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.code_validator import validate_python_syntax
from src.file_utils import slugify
from src.pipeline_models import ManifestRecord, PipelineArtifactSet

if TYPE_CHECKING:
    from src.orchestrator import PipelineRunResult


class PipelineArtifactWriter:
    """Persist final code, page objects, and a manifest as one package."""

    def __init__(self, output_dir: str = "generated_tests") -> None:
        self.output_dir = Path(output_dir)

    def write_run_artifacts(
        self,
        *,
        run_result: PipelineRunResult,
        story_text: str,
        base_url: str = "",
    ) -> PipelineArtifactSet:
        """Write one structured artifact package for a pipeline run."""
        validation_error = validate_python_syntax(run_result.final_code)
        if validation_error:
            raise ValueError(f"Generated code failed syntax validation: {validation_error}")

        package_dir = self._build_package_dir(story_text)
        pages_dir = package_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        page_object_paths: list[str] = []
        for page_object in run_result.generated_page_objects:
            page_object_path = pages_dir / Path(page_object.file_path).name
            page_object_path.write_text(page_object.module_source, encoding="utf-8")
            page_object_paths.append(str(page_object_path.absolute()))

        test_file_path = package_dir / f"test_{slugify(story_text[:50])}.py"
        test_file_path.write_text(self._build_test_file_content(run_result.final_code, base_url), encoding="utf-8")

        records = self._build_manifest_records(run_result)
        manifest_path = package_dir / "scrape_manifest.json"
        manifest_path.write_text(
            json.dumps(
                self._build_manifest_dict(
                    run_result=run_result,
                    base_url=base_url,
                    page_object_paths=page_object_paths,
                    test_file_path=str(test_file_path.absolute()),
                    records=records,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )

        return PipelineArtifactSet(
            run_id=package_dir.name,
            test_file_path=str(test_file_path.absolute()),
            page_object_paths=page_object_paths,
            manifest_path=str(manifest_path.absolute()),
            pages=run_result.scraped_page_records,
            records=records,
        )

    def _build_package_dir(self, story_text: str) -> Path:
        """Return the directory path for one generated package."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        story_slug = slugify(story_text[:50]) if story_text else "test"
        return self.output_dir / f"test_{timestamp}_{story_slug}"

    @staticmethod
    def _build_test_file_content(test_code: str, base_url: str) -> str:
        """Return the final saved test file contents with header."""
        return f'''"""
Auto-generated Playwright test package entrypoint
Generated: {datetime.now().isoformat()}
Base URL:  {base_url or "Not specified"}
"""

{test_code}
'''

    @staticmethod
    def _build_manifest_records(run_result: PipelineRunResult) -> list[ManifestRecord]:
        """Return manifest records built from unresolved placeholders."""
        records: list[ManifestRecord] = []
        for unresolved in run_result.unresolved_placeholders:
            records.append(
                ManifestRecord(
                    kind="unresolved_placeholder",
                    message=unresolved,
                )
            )
        return records

    def _build_manifest_dict(
        self,
        *,
        run_result: PipelineRunResult,
        base_url: str,
        page_object_paths: list[str],
        test_file_path: str,
        records: list[ManifestRecord],
    ) -> dict[str, Any]:
        """Return the JSON-serializable manifest structure."""
        return {
            "generated_at": datetime.now().isoformat(),
            "base_url": base_url,
            "test_file_path": test_file_path,
            "run_command": f'pytest "{test_file_path}" -v',
            "pages_scraped": [page.to_dict() for page in run_result.scraped_page_records],
            "page_requirements": [page_requirement.to_dict() for page_requirement in run_result.page_requirements],
            "journeys": [journey.to_dict() for journey in run_result.journeys],
            "page_objects": [
                {
                    "class_name": page_object.class_name,
                    "module_name": page_object.module_name,
                    "file_path": page_path,
                    "url": page_object.url,
                    "methods": page_object.methods,
                }
                for page_object, page_path in zip(run_result.generated_page_objects, page_object_paths, strict=False)
            ],
            "records": [record.to_dict() for record in records],
        }
