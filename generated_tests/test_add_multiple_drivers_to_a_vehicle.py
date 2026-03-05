# Auto-generated test for: Add multiple drivers to a vehicle
# Generated on: 2026-03-01 15:34:27.841514
#
# The locators in this test may need to be adjusted to match your current application.

from pathlib import Path
from playwright.sync_api import Page, expect


class VehicleDriversPage:
    def __init__(self, page: Page):
        self.page = page
        self.driver_name_input = page.locator("#driverNameInput")
        self.license_input = page.locator("#licenseInput")
        self.add_driver_button = page.locator("#addDriverBtn")  # Opens the form
        self.add_driver_to_list_button = page.locator("#addDriverToListBtn")  # Adds to list
        self.save_vehicle_button = page.locator("#saveVehicleBtn")
        self.cancel_driver_button = page.locator("#cancelDriverBtn")
        self.error_message = page.get_by_text("Please fill all required fields")
        self.success_message = page.get_by_text("Drivers added successfully")
        self.driver_list = page.locator("#driverList")
        self.submit_loading_state = page.locator("#submittingIndicator")
        self.main_page = page.locator("id=mainPolicyPage")
        self.add_driver_form = page.locator("id=addDriverForm")
        self.driver_list_btn = page.locator("#addDriverToListBtn")
        self.main_page_add_driver_btn = page.locator("#addDriverBtn")

    def navigate_to_page(self):
        # Navigate to the mock HTML file
        mock_file_path = Path(__file__).parent / "mock_insurance_site.html"
        self.page.goto(f"file://{mock_file_path}")

    def open_driver_form(self):
        # Navigate to the main page and open the driver form
        self.navigate_to_page()
        self.main_page_add_driver_btn.click()
        expect(self.add_driver_form).to_be_visible()

    def fill_driver_info(self, name: str, license_no: str):
        self.driver_name_input.fill(name)
        self.license_input.fill(license_no)

    def clear_fields(self):
        self.driver_name_input.clear()
        self.license_input.clear()

    def add_multiple_drivers(self, drivers: list):
        for driver in drivers:
            self.fill_driver_info(driver["name"], driver["license"])
            self.driver_list_btn.click()
            expect(self.driver_list).to_be_visible()
            self.clear_fields()

    def attempt_save_vehicle(self):
        self.save_vehicle_button.click()

    # No network mocking needed - HTML file handles all functionality client-side


def test_add_multiple_drivers_to_a_vehicle(page: Page):
    # Navigate to the mock HTML file
    mock_file_path = Path(__file__).parent / "mock_insurance_site.html"
    page.goto(f"file://{mock_file_path}")
    page.set_default_timeout(30000)

    page_obj = VehicleDriversPage(page)

    # Setup for Happy Path
    page_obj.open_driver_form()

    drivers_to_add = [
        {"name": "John Doe", "license": "123456"},
        {"name": "Jane Smith", "license": "789012"},
    ]

    # Happy Path: Add multiple valid drivers
    page_obj.add_multiple_drivers(drivers_to_add)
    page_obj.attempt_save_vehicle()

    expect(page_obj.success_message).to_be_visible()
    expect(page_obj.driver_list).to_contain_text("John Doe (123456)")
    expect(page_obj.driver_list).to_contain_text("Jane Smith (789012)")
    expect(page_obj.submit_loading_state).to_be_hidden()

    # Edge Case: Save without adding any drivers (button starts disabled)
    page_obj.open_driver_form()
    # The save button should be disabled when no drivers are added
    expect(page_obj.save_vehicle_button).to_be_disabled()

    # Edge Case: Invalid Input (Numbers in Name field)
    page_obj.fill_driver_info("123 Invalid", "9999")
    page_obj.add_driver_to_list_button.click()
    # Verify error message is shown
    expect(page_obj.error_message).to_be_visible()
    # The save button should still be disabled because we couldn't add the driver
    expect(page_obj.save_vehicle_button).to_be_disabled()


    # Edge Case: Network Errors - HTML file handles errors client-side
    # The fetch fails silently and then shows success after mock delay
    page_obj.open_driver_form()
    page_obj.fill_driver_info("Test User 2", "6666")
    page_obj.add_driver_to_list_button.click()
    
    # Verify driver was added to list
    expect(page_obj.driver_list).to_contain_text("Test User 2 (6666)")
    page_obj.attempt_save_vehicle()
    
    # In the mock HTML, the fetch fails silently but success is still shown
    expect(page_obj.success_message).to_be_visible()
    expect(page_obj.submit_loading_state).to_be_hidden()
