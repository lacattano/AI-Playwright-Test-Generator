"""Parse placeholder-based skeleton code produced by the intelligent pipeline."""

from __future__ import annotations

import re

from src.pipeline_models import PageRequirement, PlaceholderUse, TestJourney, TestStep


class SkeletonParser:
    """Extract placeholders and required URLs from generated skeletons."""

    def __init__(self) -> None:
        self.placeholder_pattern = re.compile(r"\{\{(CLICK|FILL|GOTO|URL|ASSERT):([^}]+)\}\}")
        self.pages_pattern = re.compile(r"#\s*-\s*(https?://[^\s]+)(?:\s+\((.*?)\))?")
        self.single_brace_placeholder_pattern = re.compile(r"(?<!\{)\{(CLICK|FILL|GOTO|URL|ASSERT):([^}]+)\}(?!\})")
        self.test_definition_pattern = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.M)
        self.page_object_reference_pattern = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\s*\(")

    def parse_placeholders(self, code: str) -> list[tuple[str, str]]:
        """Return all placeholder action-description pairs."""
        return [(action, description.strip()) for action, description in self.placeholder_pattern.findall(code)]

    def parse_placeholder_uses(self, code: str) -> list[PlaceholderUse]:
        """Return structured placeholder occurrences with line information."""
        placeholder_uses: list[PlaceholderUse] = []

        for line_number, line in enumerate(code.splitlines(), start=1):
            for action, description in self.placeholder_pattern.findall(line):
                clean_description = description.strip()
                placeholder_uses.append(
                    PlaceholderUse(
                        action=action,
                        description=clean_description,
                        token=f"{{{{{action}:{clean_description}}}}}",
                        line_number=line_number,
                        raw_line=line,
                    )
                )

        return placeholder_uses

    def parse_pages_needed(self, code: str) -> list[tuple[str, str]]:
        """Return the pages listed in the `# PAGES_NEEDED:` block."""
        return [(url.strip(), desc.strip() if desc else "") for url, desc in self.pages_pattern.findall(code)]

    def parse_page_requirements(self, code: str) -> list[PageRequirement]:
        """Return typed page requirements from the `# PAGES_NEEDED:` block."""
        return [PageRequirement(url=url, description=description) for url, description in self.parse_pages_needed(code)]

    def parse_test_journeys(self, code: str) -> list[TestJourney]:
        """Return structured journey data for each generated test function."""
        lines = code.splitlines()
        matches = list(self.test_definition_pattern.finditer(code))
        if not matches:
            return []

        line_offsets = self._build_line_offsets(lines)
        journeys: list[TestJourney] = []

        for index, match in enumerate(matches):
            test_name = match.group(1)
            start_line = self._offset_to_line(line_offsets, match.start())
            next_match_start = matches[index + 1].start() if index + 1 < len(matches) else len(code)
            end_line = self._offset_to_line(line_offsets, next_match_start) - (0 if index + 1 == len(matches) else 1)
            block_lines = lines[start_line - 1 : end_line]
            steps = self._build_steps(block_lines, start_line)
            page_object_names = self._extract_page_object_names(block_lines)

            journeys.append(
                TestJourney(
                    test_name=test_name,
                    start_line=start_line,
                    end_line=end_line,
                    page_object_names=page_object_names,
                    steps=steps,
                )
            )

        return journeys

    @staticmethod
    def _build_line_offsets(lines: list[str]) -> list[int]:
        """Return the starting character offset for each line."""
        offsets: list[int] = []
        running_offset = 0
        for line in lines:
            offsets.append(running_offset)
            running_offset += len(line) + 1
        return offsets

    @staticmethod
    def _offset_to_line(line_offsets: list[int], offset: int) -> int:
        """Convert a character offset into a 1-based line number."""
        line_number = 1
        for index, line_offset in enumerate(line_offsets, start=1):
            if line_offset > offset:
                break
            line_number = index
        return line_number

    def _build_steps(self, block_lines: list[str], start_line: int) -> list[TestStep]:
        """Build ordered steps for one test function block."""
        steps: list[TestStep] = []

        for index, line in enumerate(block_lines, start=0):
            raw_line = line.rstrip()
            if not raw_line.strip() or raw_line.lstrip().startswith("#") or raw_line.lstrip().startswith("def "):
                continue

            placeholders: list[PlaceholderUse] = []
            for action, description in self.placeholder_pattern.findall(raw_line):
                clean_description = description.strip()
                placeholders.append(
                    PlaceholderUse(
                        action=action,
                        description=clean_description,
                        token=f"{{{{{action}:{clean_description}}}}}",
                        line_number=start_line + index,
                        raw_line=raw_line,
                    )
                )

            steps.append(
                TestStep(
                    line_number=start_line + index,
                    raw_line=raw_line,
                    placeholders=placeholders,
                )
            )

        return steps

    def _extract_page_object_names(self, block_lines: list[str]) -> list[str]:
        """Return page object classes referenced within a test block."""
        page_object_names: list[str] = []
        seen: set[str] = set()

        for line in block_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            for name in self.page_object_reference_pattern.findall(line):
                if not name.endswith("Page"):
                    continue
                if name not in seen:
                    seen.add(name)
                    page_object_names.append(name)

        return page_object_names

    def get_test_class_names(self, code: str) -> list[str]:
        """Return class names declared in the skeleton."""
        return re.findall(r"class\s+(\w+):", code)

    def find_malformed_placeholders(self, code: str) -> list[str]:
        """Return placeholders that incorrectly use single braces."""
        return [
            f"{{{action}:{description.strip()}}}"
            for action, description in self.single_brace_placeholder_pattern.findall(code)
        ]

    def validate_skeleton(self, code: str) -> str | None:
        """Return a user-facing validation error for malformed skeleton output."""
        malformed_placeholders = self.find_malformed_placeholders(code)
        if malformed_placeholders:
            preview = ", ".join(malformed_placeholders[:3])
            return (
                f"Skeleton output used invalid single-brace placeholders instead of `{{{{...}}}}`. Examples: {preview}"
            )

        pages_needed_block = re.search(r"#\s*PAGES_NEEDED:\s*(.*)", code, re.S)
        if pages_needed_block:
            page_lines = re.findall(r"^\s*#\s*-\s*(.+)$", pages_needed_block.group(1), re.M)
            invalid_pages = [
                line.strip() for line in page_lines if line.strip() and not re.match(r"https?://", line.strip())
            ]
            if invalid_pages:
                preview = ", ".join(invalid_pages[:3])
                return (
                    "Skeleton output listed invalid page entries in `# PAGES_NEEDED:`. "
                    "Each entry must be a real absolute URL. "
                    f"Examples: {preview}"
                )

        return None
