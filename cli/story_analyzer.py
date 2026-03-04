"""
Story Analyzer for AI Playwright Test Generator.

This module provides intelligent analysis of user stories to:
- Enrich test cases with missing information
- Identify test data requirements
- Suggest optimal test sequence
- Detect dependencies between test cases
- Generate preconditions automatically

Supports both fast (regex-based) and thorough (LLM-powered) analysis modes.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cli.config import AnalysisMode, config
from cli.input_parser import ParsedInput, TestCase


@dataclass
class AnalyzedTestCase(TestCase):
    """Enhanced test case with analysis results."""

    # Original fields inherited from TestCase
    identified_actions: list[str] = field(default_factory=list)
    identified_expectations: list[str] = field(default_factory=list)
    suggested_data: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    estimated_complexity: str = "low"  # low, medium, high
    analysis_confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            **super().to_dict(),
            "identified_actions": self.identified_actions,
            "identified_expectations": self.identified_expectations,
            "suggested_data": self.suggested_data,
            "dependencies": self.dependencies,
            "estimated_complexity": self.estimated_complexity,
            "analysis_confidence": self.analysis_confidence,
        }


@dataclass
class AnalysisResult:
    """Container for analysis results."""

    analyzed_test_cases: list[AnalyzedTestCase]
    analysis_summary: dict = field(default_factory=dict)
    detected_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "analyzed_test_cases": [tc.to_dict() for tc in self.analyzed_test_cases],
            "analysis_summary": self.analysis_summary,
            "detected_patterns": self.detected_patterns,
            "analysis_timestamp": datetime.now().isoformat(),
        }

    def save_to_json(self, output_path: str) -> str:
        """Save analysis results to JSON file."""
        data = self.to_dict()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        return output_path


class KeywordAnalyzer:
    """Analyze text for key test elements using keywords."""

    ACTION_KEYWORDS = {
        "navigation": ["click", "navigate", "go to", "open", "enter", "load"],
        "data_interaction": ["enter", "type", "fill", "input", "upload", "download"],
        "confirmation": ["confirm", "approve", "accept", "decline", "reject"],
        "search": ["search", "find", "query", "lookup"],
        "filter": ["filter", "sort", "sort by", "order by"],
        "form": ["submit", "save", "create", "update", "delete", "edit"],
    }

    EXPECTATION_KEYWORDS = {
        "success": ["success", "successfully", "valid", "approved", "confirmed"],
        "error": ["error", "fail", "failed", "invalid", "unauthorized", "forbidden"],
        "redirect": ["redirect", "navigate", "go to", "go to", "move to"],
        "state_change": ["updated", "saved", "created", "deleted", "modified"],
        "visibility": ["visible", "appear", "show", "display", "highlighted"],
        "content": ["contains", "includes", "displays", "shows", "presents"],
    }

    @classmethod
    def identify_actions(cls, text: str) -> list[str]:
        """Identify action types from text."""
        text_lower = text.lower()
        actions = []

        for action_type, keywords in cls.ACTION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                actions.append(action_type)

        # Add general action if none identified
        if not actions and any(kw in text_lower for kw in ["click", "enter", "select", "choose"]):
            actions.append("general")

        return actions

    @classmethod
    def identify_expectations(cls, text: str) -> list[str]:
        """Identify expected outcomes from text."""
        text_lower = text.lower()
        expectations = []

        for exp_type, keywords in cls.EXPECTATION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                expectations.append(exp_type)

        return expectations or ["result_display"]


class DataRequirementAnalyzer:
    """Analyze and suggest test data requirements."""

    DATA_PATTERNS = {
        "email": r"\b[\w.-]+@[\w.-]+\.\w+\b",
        "username": r"\b(?:user|account|member)\s*[:\s]*\s*\w+\b",
        "password": r"\b(?:password|pwd)\s*[:\s]*\s*\S+",
        "name": r"\b(?:full\s*name|first\s*name|last\s*name|display\s*name)\s*[:\s]*\s*[\w\s]+",
        "url": r"https?://[^\s]+",
        "id": r"\b(?:id|key)\s*[:\s]*\s*[\w-]+\b",
        "amount": r"\b(?:amount|total|price|cost)\s*[:\s]*\s*[£$€]?\d+([.,]\d+)?\b",
    }

    DATA_CATEGORIES = {
        "auth": ["login", "logout", "register", "sign up", "password", "email"],
        "form": ["form", "submit", "field", "input", "entry"],
        "navigation": ["page", "screen", "view", "dashboard", "menu"],
        "data": ["data", "record", "item", "item", "resource", "object"],
        "error": ["error", "invalid", "failure", "exception", "unauthorized"],
    }

    @classmethod
    def suggest_data(cls, text: str) -> dict[str, Any]:
        """Suggest test data based on content."""
        text_lower = text.lower()
        suggested_data: dict[str, Any] = {}

        # Detect data categories needed
        categories = []
        for category, keywords in cls.DATA_CATEGORIES.items():
            if any(kw in text_lower for kw in keywords):
                categories.append(category)

        # Generate specific data suggestions
        if "email" in text_lower or "register" in text_lower or "login" in text_lower:
            suggested_data["email"] = cls._generate_test_email()
            suggested_data["password"] = "TestP@ssw0rd123!"

        if "form" in categories or "submit" in text_lower:
            suggested_data["form_data"] = {"name": "Test User", "email": cls._generate_test_email()}

        if any(kw in text_lower for kw in ["payment", "price", "cost", "amount"]):
            suggested_data["amount"] = "99.99"
            suggested_data["currency"] = "USD"

        return suggested_data if suggested_data else {}

    @classmethod
    def _generate_test_email(cls) -> str:
        """Generate a unique test email."""
        return f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"


class DependencyAnalyzer:
    """Analyze dependencies between test cases."""

    COMMON_PRECONDITIONS = [
        "login",
        "authentication",
        "be logged in",
        "be authenticated",
        "create account",
        "register",
        "sign up",
        "navigate to login",
    ]

    COMMON_POSTCONDITIONS = ["logout", "clear form", "reset", "navigate to home", "go home"]

    @classmethod
    def identify_dependencies(cls, test_case: TestCase, all_cases: list[TestCase]) -> list[str]:
        """Identify dependencies for a test case."""
        dependencies: list[str] = []
        text_lower = test_case.description.lower()

        # Check for explicit preconditions
        if test_case.preconditions:
            dependencies.extend(test_case.preconditions)

        # Check for implicit preconditions
        for condition in cls.COMMON_PRECONDITIONS:
            if condition in text_lower:
                dependencies.append(f"Required: {condition.capitalize()}")

        # Check for sequential dependencies
        for other_case in all_cases:
            if other_case == test_case:
                continue

            # Check if this test needs something from another test
            text_lower_other = other_case.description.lower()
            title_other = other_case.title.lower()

            # Find creating actions that might be needed
            creating_actions = ["create", "register", "add", "submit", "save"]
            using_actions = ["use", "select", "open", "edit", "update"]

            if any(action in text_lower for action in using_actions):
                if any(action in text_lower_other for action in creating_actions):
                    dependencies.append(f"Depends on: {title_other[:50]}")

        # Check for cleanup needs (postconditions)
        for postcond in cls.COMMON_POSTCONDITIONS:
            if postcond in text_lower:
                dependencies.append(f"Cleanup: {postcond.capitalize()}")

        return list(set(dependencies))


class ComplexityEstimator:
    """Estimate test complexity based on content."""

    LOW_COMPLEXITY_KEYWORDS = ["view", "display", "show", "navigate to", "open"]
    MEDIUM_COMPLEXITY_KEYWORDS = ["enter", "fill", "click", "submit", "select", "filter"]
    HIGH_COMPLEXITY_KEYWORDS = ["validate", "verify", "assert", "compare", "calculate", "process", "integrate"]

    @classmethod
    def estimate(cls, text: str) -> str:
        """Estimate test complexity."""
        text_lower = text.lower()

        # Count keyword matches
        low_count = sum(1 for kw in cls.LOW_COMPLEXITY_KEYWORDS if kw in text_lower)
        medium_count = sum(1 for kw in cls.MEDIUM_COMPLEXITY_KEYWORDS if kw in text_lower)
        high_count = sum(1 for kw in cls.HIGH_COMPLEXITY_KEYWORDS if kw in text_lower)

        total = low_count + medium_count + high_count

        if total == 0:
            return "low"

        if high_count > medium_count:
            return "high"
        elif high_count > 0 or medium_count >= 3:
            return "medium"
        else:
            return "low"


class UserStoryAnalyzer:
    """Comprehensive user story analyzer with multiple analysis modes."""

    def __init__(self, analysis_mode: AnalysisMode | None = None):
        """
        Initialize analyzer.

        Args:
            analysis_mode: How to perform analysis (fast vs thorough)
        """
        self.analysis_mode: AnalysisMode = analysis_mode or config.LLM_ANALYSIS_MODE

    def analyze(self, parsed_input: ParsedInput) -> AnalysisResult:
        """
        Analyze parsed test cases.

        Args:
            parsed_input: Parsed input from InputParser

        Returns:
            AnalysisResult with enriched test cases
        """
        analyzed_cases = []
        detected_patterns = []

        for test_case in parsed_input.test_cases:
            analyzed = self._analyze_test_case(test_case, parsed_input.test_cases)
            analyzed_cases.append(analyzed)

            # Collect detected patterns
            detected_patterns.extend(analyzed.identified_actions)
            detected_patterns.extend(analyzed.identified_expectations)

        # Create summary
        summary = {
            "total_cases": len(analyzed_cases),
            "complexity_distribution": self._calculate_complexity_distribution(analyzed_cases),
            "detected_actions": list({a for case in analyzed_cases for a in case.identified_actions}),
            "detected_expectations": list({e for case in analyzed_cases for e in case.identified_expectations}),
            "requires_auth": any(
                "login" in case.description.lower() or "authentication" in case.description.lower()
                for case in analyzed_cases
            ),
            "analysis_timestamp": datetime.now().isoformat(),
        }

        return AnalysisResult(
            analyzed_test_cases=analyzed_cases, analysis_summary=summary, detected_patterns=list(set(detected_patterns))
        )

    def _analyze_test_case(self, test_case: TestCase, all_cases: list[TestCase]) -> AnalyzedTestCase:
        """Analyze a single test case."""
        # Identify actions and expectations
        actions = KeywordAnalyzer.identify_actions(test_case.description)
        expectations = KeywordAnalyzer.identify_expectations(test_case.description)

        # Suggest data requirements
        suggested_data = DataRequirementAnalyzer.suggest_data(test_case.description)

        # Identify dependencies
        dependencies = DependencyAnalyzer.identify_dependencies(test_case, all_cases)

        # Estimate complexity
        complexity = ComplexityEstimator.estimate(test_case.description)

        # Determine confidence based on analysis completeness
        confidence = self._calculate_confidence(actions, expectations, suggested_data)

        # Create analyzed test case
        analyzed = AnalyzedTestCase(
            title=test_case.title,
            description=test_case.description,
            preconditions=test_case.preconditions,
            test_data=test_case.test_data,
            expected_outcome=test_case.expected_outcome,
            test_type=test_case.test_type,
            priority=test_case.priority,
            identified_actions=actions,
            identified_expectations=expectations,
            suggested_data=suggested_data,
            dependencies=dependencies,
            estimated_complexity=complexity,
            analysis_confidence=confidence,
        )

        return analyzed

    def _calculate_confidence(self, actions: list[str], expectations: list[str], data: dict) -> float:
        """Calculate analysis confidence score."""
        base_confidence = 1.0

        # Deduct points for missing elements
        if not actions:
            base_confidence -= 0.2
        if not expectations:
            base_confidence -= 0.2
        if not data:
            base_confidence -= 0.1

        return max(0.5, base_confidence)

    def _calculate_complexity_distribution(self, cases: list[AnalyzedTestCase]) -> dict[str, Any]:
        """Calculate complexity distribution."""
        distribution = {"low": 0, "medium": 0, "high": 0}

        for case in cases:
            distribution[case.estimated_complexity] += 1

        total = len(cases)
        if total > 0:
            return {k: f"{v}/{total} ({v / total * 100:.1f}%)" for k, v in distribution.items()}
        return distribution


class PatternAnalyzer:
    """Detect common testing patterns in user stories."""

    PATTERN_DETECTIONS: dict[str, re.Pattern[str]] = {
        "data_table": re.compile(r"@\d+|[^\n]*\|[^\n]*\|"),
        "parametrization": re.compile(r"(\w+)\s+(?:with|as|using)\s+([^\n]+)"),
        "conditional": re.compile(r"(?:if|when|unless|whenever|in case)\s+.*?(?:then|else|else if|otherwise)"),
        "loop": re.compile(r"for each|loop through|repeatedly|multiple times"),
        "state_change": re.compile(r"becomes|changes to|transitions|updates to|moves to"),
        "validation": re.compile(r"validat|valid|should not|cannot|must not"),
        "performance": re.compile(r"within|under|less than|response time|load|time.*?\d"),
    }

    @classmethod
    def detect_patterns(cls, text: str) -> list[str]:
        """Detect patterns in test text."""
        detected: list[str] = []

        for pattern_name, pattern_re in cls.PATTERN_DETECTIONS.items():
            if pattern_re.search(text):
                detected.append(pattern_name)

        return detected


class InputEnricher:
    """Enrich user input with intelligent suggestions."""

    def __init__(self, analysis_mode: AnalysisMode | None = None):
        self.analyzer = UserStoryAnalyzer(analysis_mode)

    def enrich(self, text: str, explicit_format: str | None = None) -> AnalysisResult:
        """
        Enrich raw input with analysis.

        Args:
            text: Raw input text
            explicit_format: Optional explicit format specification

        Returns:
            AnalysisResult with enriched test cases
        """
        # Parse first
        from cli.input_parser import InputParser

        parser = InputParser()
        explicit_format_str = explicit_format if explicit_format else "user_story"
        parsed = parser.parse(text, explicit_format_str)

        # Then analyze
        return self.analyzer.analyze(parsed)


# Convenience functions
def analyze_user_story(story: str, analysis_mode: AnalysisMode | None = None) -> AnalysisResult:
    """Analyze a single user story."""
    enricher = InputEnricher(analysis_mode)
    return enricher.enrich(story)


def analyze_test_suite(test_cases: list[TestCase]) -> AnalysisResult:
    """Analyze a complete test suite."""
    from cli.input_parser import ParsedInput

    analyzer = UserStoryAnalyzer()
    parsed = ParsedInput(test_cases=test_cases, source_format="manual", raw_input="", metadata={})
    return analyzer.analyze(parsed)
