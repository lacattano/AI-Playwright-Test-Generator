import pytest
from playwright.sync_api import Page, expect


class TestHappyPath:
    """Auto-generated test class for happy_path scenarios.
    Generated from AI Playwright Test Generator on 2026-03-03 22:27:04
    Source analysis: 1 test cases
    """

    def test_main_flow(self, page: Page) -> None:
        """Test: Main Flow
        Description: As a user, I want to login with email and password
        """
        # Login steps
        page.goto("http://localhost:8080")
        page.fill('[data-testid="email"]', "test_20260303_222704@example.com")
        page.fill('[data-testid="password"]', "TestP@ssw0rd123!")
        page.click('[data-testid="login-button"]')

        # Verify login succeeded
        expect(page.locator('[data-testid="result_display"]')).to_be_visible()
