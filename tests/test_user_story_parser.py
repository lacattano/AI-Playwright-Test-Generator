#!/usr/bin/env python3
"""Tests for the user story parser module."""

from typing import Any

from src.user_story_parser import FeatureParser, FeatureSpecification


class TestFeatureSpecification:
    """Tests for FeatureSpecification dataclass."""

    def test_criteria_count_property(self) -> None:
        """Test that criteria_count returns correct length."""
        spec = FeatureSpecification(
            user_story="As a user I want to login",
            acceptance_criteria=["login form exists", "enter username"],
            raw_input="test input",
        )
        assert spec.criteria_count == 2

    def test_to_dict_method(self) -> None:
        """Test that to_dict returns correct dictionary format."""
        spec = FeatureSpecification(
            user_story="As a user I want to login",
            acceptance_criteria=["login form exists", "enter username"],
            raw_input="test input",
        )
        result: dict[str, Any] = spec.to_dict()
        assert result["user_story"] == "As a user I want to login"
        assert result["acceptance_criteria"] == ["login form exists", "enter username"]
        assert result["criteria_count"] == 2


class TestFeatureParser:
    """Tests for FeatureParser class."""

    def test_parse_structured_gherkin(self) -> None:
        """Test parsing structured Gherkin-style feature spec."""
        parser = FeatureParser()
        text = """
## User Story
As a user I want to log in so that I can access my account.

## Acceptance Criteria
- Login form is displayed
- User can enter username and password
- Clicking LOGIN redirects to the inventory page
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert "As a user I want to log in" in spec.user_story
        assert len(spec.acceptance_criteria) == 3
        assert "Login form is displayed" in spec.acceptance_criteria

    def test_parse_with_jira_style_bullets(self) -> None:
        """Test parsing Jira-style feature spec with bullet points."""
        parser = FeatureParser()
        text = """## User Story
As a shopper I want to add items to cart.

## Acceptance Criteria
* Add item to cart button visible
* Cart counter updates when item added
* Empty cart message shows when cart is empty
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert len(spec.acceptance_criteria) == 3

    def test_parse_with_numbered_list(self) -> None:
        """Test parsing numbered list format."""
        parser = FeatureParser()
        text = """User Story: As a user I want to search for products

Acceptance Criteria:
1. Search bar is visible on homepage
2. Enter search term filters results
3. No results message shows for invalid search
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert len(spec.acceptance_criteria) == 3
        assert "Search bar is visible on homepage" in spec.acceptance_criteria

    def test_parse_without_headings(self) -> None:
        """Test fallback when no section headings found."""
        parser = FeatureParser()
        text = """As a user I want to log in so I can access my account.
The login form must be displayed.
User must be able to enter credentials.
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert "As a user I want to log in" in spec.user_story
        # Everything treated as user story when no headings
        assert len(spec.acceptance_criteria) == 0

    def test_parse_empty_input(self) -> None:
        """Test that empty input returns error."""
        parser = FeatureParser()
        result = parser.parse("")
        assert result.success is False
        assert result.error_message == "Input cannot be empty"
        assert result.specification is None

    def test_parse_whitespace_only_input(self) -> None:
        """Test that whitespace-only input returns error."""
        parser = FeatureParser()
        result = parser.parse("   \n\n  \n")
        assert result.success is False
        assert result.error_message == "Input cannot be empty"

    def test_parse_no_user_story_found(self) -> None:
        """Test error when user story cannot be extracted."""
        parser = FeatureParser()
        text = """## Acceptance Criteria
- Some criterion
"""
        result = parser.parse(text)
        assert result.success is False
        assert result.error_message == "No user story found in input"

    def test_parse_cleans_bullets_from_criteria(self) -> None:
        """Test that bullet markers are removed from criteria."""
        parser = FeatureParser()
        text = """## User Story
Test story

## Acceptance Criteria
- Bullet item one
* Asterisk item two
• Dotted item three
1. Numbered item four
2. Numbered item five
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        # Bullets should be stripped
        assert spec.acceptance_criteria == [
            "Bullet item one",
            "Asterisk item two",
            "Dotted item three",
            "Numbered item four",
            "Numbered item five",
        ]

    def test_parse_with_hash_mark_dividers(self) -> None:
        """Test that hash mark dividers are ignored."""
        parser = FeatureParser()
        text = """
---

## User Story
As a user I want to login

---

## Acceptance Criteria
- Login form exists
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        assert len(result.specification.acceptance_criteria) == 1

    def test_parse_alternative_criteria_heading_acceptance(self) -> None:
        """Test parsing with 'Acceptance' as criteria heading."""
        parser = FeatureParser()
        text = """## User Story
Test story

## Acceptance
- Criterion one
- Criterion two
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        assert len(result.specification.acceptance_criteria) == 2

    def test_parse_alternative_criteria_heading_criteria(self) -> None:
        """Test parsing with 'Criteria' as criteria heading."""
        parser = FeatureParser()
        text = """## User Story
Test story

## Criteria
- Criterion one
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        assert len(result.specification.acceptance_criteria) == 1

    def test_parse_ac_colon_notation(self) -> None:
        """Test parsing with 'AC:' notation."""
        parser = FeatureParser()
        text = """## User Story
Test story

AC:
- Criterion one
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        assert len(result.specification.acceptance_criteria) == 1

    def test_parse_requirements_heading(self) -> None:
        """Test parsing with 'Requirements' as criteria heading."""
        parser = FeatureParser()
        text = """## User Story
Test story

## Requirements
- Requirement one
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        assert len(result.specification.acceptance_criteria) == 1

    def test_parse_preserves_raw_input(self) -> None:
        """Test that raw_input is preserved in specification."""
        parser = FeatureParser()
        original = "## User Story\ntest\n\n## Criteria\n- criterion"
        result = parser.parse(original)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert spec.raw_input == original

    def test_parse_as_a_story_heading(self) -> None:
        """Test parsing with 'As a' as story heading."""
        parser = FeatureParser()
        text = """## As a
As a user I want to login

## Acceptance Criteria
- Login works
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert "As a user I want to login" in spec.user_story

    def test_parse_story_heading(self) -> None:
        """Test parsing with 'Story' as story heading."""
        parser = FeatureParser()
        text = """## Story
Test story

## Acceptance Criteria
- Criterion one
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert "Test story" in spec.user_story

    def test_parse_with_extra_whitespace(self) -> None:
        """Test that extra whitespace is handled correctly."""
        parser = FeatureParser()
        text = """
        ##   User Story
        As a user I want to login
        ##   Acceptance Criteria
        - Criterion one
        - Criterion two
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert len(spec.acceptance_criteria) == 2

    def test_parse_multiple_headings_same_section(self) -> None:
        """Test that multiple similar headings don't cause issues."""
        parser = FeatureParser()
        text = """## User Story
Test story

## User Story (continued)
Additional story text

## Acceptance Criteria
- Criterion one
"""
        result = parser.parse(text)
        assert result.success is True
        assert result.specification is not None
        spec = result.specification
        assert "Test story" in spec.user_story
        assert "Additional story text" in spec.user_story

    def test_parse_returns_parse_result_with_success_false_on_error(self) -> None:
        """Test that ParseResult has correct structure on error."""
        parser = FeatureParser()
        result = parser.parse("")
        assert hasattr(result, "success")
        assert hasattr(result, "specification")
        assert hasattr(result, "error_message")
        assert result.success is False
        assert result.specification is None
        assert result.error_message is not None
