# Auto-generated test for: Add multiple drivers to a vehicle
# Generated on: 2026-03-01 15:34:27.841514
#
# The locators in this test may need to be adjusted to match your current application.

from playwright.sync_api import Page, expect

class VehicleDriversPage:
    def __init__(self, page: Page):
        self.page = page
        self.driver_name_input = page.get_by_label("Driver Name")
        self.license_input = page.get_by_label("License Number")
        self.add_driver_button = page.get_by_role("button", name="Add Driver")
        self.save_vehicle_button = page.get_by_role("button", name="Save Vehicle")
        self.error_message = page.get_by_text("Please fill all required fields")
        self.success_message = page.get_by_text("Drivers added successfully")
        self.driver_list = page.get_by_role("list", name="Assigned Drivers")
        self.submit_loading_state = page.get_by_label("Submitting")

    def navigate_to_page(self):
        self.page.goto("https://example.com/vehicles/create")

    def fill_driver_info(self, name: str, license_no: str):
        self.driver_name_input.fill(name)
        self.license_input.fill(license_no)

    def clear_fields(self):
        self.driver_name_input.clear()
        self.license_input.clear()

    def add_multiple_drivers(self, drivers: list):
        for driver in drivers:
            self.fill_driver_info(driver["name"], driver["license"])
            self.add_driver_button.click()
            expect(self.driver_list).to_be_visible()
            self.clear_fields()

    def attempt_save_vehicle(self):
        self.save_vehicle_button.click()

    def expect_network_request(self, is_success: bool = True):
        self.page.route("https://example.com/api/vehicles", lambda route: (
            route.fulfill(status=200, body='{"status": "success"}') if is_success else route.fulfill(status=500, body='{"error": "server failure"}')
        ))

def test_add_multiple_drivers_to_a_vehicle(page: Page):
    page.goto("http://localhost:8080")
    page.set_default_timeout(30000)
    
    page_obj = VehicleDriversPage(page)
    
    # Setup for Happy Path
    page_obj.navigate_to_page()
    
    # Mock successful API call for happy path
    page.route("https://example.com/api/vehicles", lambda route: route.fulfill(
        status=200, 
        body='{"status": "success"}'
    ))

    drivers_to_add = [
        {"name": "John Doe", "license": "123456"},
        {"name": "Jane Smith", "license": "789012"}
    ]
    
    # Happy Path: Add multiple valid drivers
    page_obj.add_multiple_drivers(drivers_to_add)
    page_obj.attempt_save_vehicle()
    
    expect(page_obj.success_message).to_be_visible()
    expect(page_obj.driver_list).to_have_text("John Doe (123456)")
    expect(page_obj.driver_list).to_have_text("Jane Smith (789012)")
    expect(page_obj.submit_loading_state).to_be_disabled()

    # Edge Case: Empty Fields
    page_obj.navigate_to_page()
    page_obj.clear_fields()
    page_obj.attempt_save_vehicle()
    
    expect(page_obj.error_message).to_be_visible()
    expect(page_obj.save_vehicle_button).to_be_disabled()

    # Edge Case: Invalid Input (Numbers in Name field)
    page_obj.navigate_to_page()
    page_obj.driver_name_input.fill("123 Invalid")
    page_obj.license_input.fill("9999")
    page_obj.attempt_save_vehicle()
    
    expect(page_obj.driver_name_input).to_have_value("123 Invalid")
    expect(page_obj.error_message).to_be_visible()

    # Edge Case: Network Errors
    page_obj.navigate_to_page()
    page.route("https://example.com/api/vehicles", lambda route: route.fulfill(
        status=500, 
        body='{"error": "server failure"}'
    ))
    
    page_obj.fill_driver_info("Test User", "5555")
    page_obj.add_driver_button.click()
    page_obj.attempt_save_vehicle()
    
    expect(page_obj.error_message).to_have_text("Failed to connect to server")
    expect(page_obj.submit_loading_state).to_be_disabled()
    page.close()