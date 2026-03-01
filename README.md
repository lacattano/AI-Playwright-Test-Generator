# AI Playwright Test Generator

An AI-powered tool that generates Playwright Python test scripts using local LLM models via Ollama. This project helps automate the creation of modern, async Playwright tests based on natural language descriptions.

## Features

- **AI-Powered Test Generation**: Generate Playwright tests from simple text descriptions using local LLM models
- **Local LLM Support**: Runs entirely locally using Ollama (no API costs or data privacy concerns)
- **Async Test Generation**: Creates modern async/await Playwright tests by default
- **Page Object Model (POM)**: Generated tests follow POM pattern with reusable page classes
- **Mock Site Generation**: Includes a built-in mock insurance website for testing against
- **Screenshot Capture**: Automatically captures screenshots for test evidence (entry, steps, success, failures)
- **Flexible Configuration**: Supports multiple LLM models with environment variable configuration
- **Robust Error Handling**: Validates permissions and provides clear error messages
- **Customizable Output**: Save generated tests to a configurable output directory
- **Interactive CLI**: Menu-driven interface for easy test generation

## Prerequisites

1. **Python 3.13+**: This project requires Python 3.13 or higher
2. **Ollama**: A local LLM server that runs various models
   - Download from: https://ollama.com
   - Install Ollama on your system
3. **Ollama Model**: Download a compatible model (recommended: `qwen3.5:35b` for generation quality)
   ```bash
   ollama pull qwen3.5:35b
   ```

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd vs-projects
   ```

2. Install dependencies:
   ```bash
   uv sync
   # or
   pip install -r requirements.txt
   ```

3. Ensure Ollama is running:
   ```bash
   ollama serve
   ```

## Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `OLLAMA_MODEL` | The Ollama model to use for test generation | `qwen3.5:35b` | `qwen2.5:7b` |
| `OLLAMA_TIMEOUT` | Request timeout in seconds | `60` | `120` |

To set environment variables:

**Windows (PowerShell):**
```powershell
$env:OLLAMA_MODEL="qwen2.5:7b"
$env:OLLAMA_TIMEOUT="120"
```

**Windows (Command Prompt):**
```cmd
set OLLAMA_MODEL=qwen2.5:7b
set OLLAMA_TIMEOUT=120
```

**Linux/macOS:**
```bash
export OLLAMA_MODEL=qwen2.5:7b
export OLLAMA_TIMEOUT=120
```

## Usage

### Quick Start - Interactive Mode

1. **Make sure Ollama is running** (in a separate terminal):
   ```bash
   ollama serve
   ```

2. **Run the generator**:
   ```bash
   # PowerShell
   $env:OLLAMA_MODEL="qwen3.5:35b"
   python main.py
   ```

3. **Choose an option**:
   ```
   AI Playwright Test Generator
   ============================================
   Options:
   [1] Generate Playwright test (standard mode)
   [2] Generate test with auto-open mock site
   [3] Start mock server only
   [4] Generate test (headless, no UI)
   [x] Exit
   
   Choose an option: 
   ```

4. **Enter your test scenario** when prompted:
   ```
   Enter the feature to test (e.g., 'User Login', 'Checkout Process'): Log in to the site with email and password
   ```

### Using the Mock Site

Option [2] generates a test while opening the mock site in your browser. The mock site simulates an insurance portal with:
- Login page
- Home dashboard
- Policy management
- Vehicle lookup
- Claims submission

To use only the mock site:
```bash
# Option [3] - Start mock server
Choose an option: 3
```

### Python Script Usage

You can use the generator programmatically in your own Python scripts:

```python
from src.test_generator import TestGenerator

# Initialize the generator (uses default model and output directory)
generator = TestGenerator()

# Generate a test
user_request = "Log in to the insurance portal and add a new vehicle to a policy"
file_path = generator.generate_and_save(user_request)

print(f"Test saved to: {file_path}")
```

### Custom Configuration

**Custom Model:**
```python
generator = TestGenerator(model_name="qwen2.5:7b")
```

**Custom Output Directory:**
```python
generator = TestGenerator(output_dir="my_tests")
```

### Running Generated Tests

Generated tests are saved to `generated_tests/` with a timestamped filename:

```bash
# Run a specific test
python generated_tests/test_20260301_143000_login_feature.py

# Run all tests
python -m pytest generated_tests/

# Run with screenshots
playwright test generated_tests/ --screenshot=on
```

## Output Format

### Generated Test Structure

The generated tests follow these conventions:

- **Filename Format**: `test_YYYYMMDD_HHMMSS_<description>.py`
- **Code Style**: Modern async/await Playwright tests
- **Pattern**: Page Object Model (POM) with reusable page classes
- **Locators**: Semantic selectors (get_by_role, get_by_label, get_by_text)
- **Assertions**: Playwright assertions for validation

### Example Generated Test

```python
# Auto-generated test for: Login Feature
# Generated on: 2026-03-01 14:30:00
# The locators in this test may need to be adjusted to match your current application.

from playwright.sync_api import Page, expect

class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        self.email_input = page.get_by_label("Email Address")
        self.password_input = page.get_by_label("Password")
        self.login_button = page.get_by_role("button", name="Login")
        self.error_message = page.get_by_text("Invalid credentials")
        self.dashboard = page.get_by_text("Dashboard")
    
    def login(self, email: str, password: str) -> None:
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.login_button.click()

def test_login_success(page: Page):
    """Test successful login with valid credentials."""
    page.goto("http://localhost:8080")
    page.set_default_timeout(30000)
    
    page = LoginPage(page)
    page.login("test@example.com", "password123")
    
    expect(page.dashboard).to_be_visible(timeout=5000)
    expect(page.login_button).to_be_disabled()

def test_login_invalid_credentials(page: Page):
    """Test login with invalid credentials shows error message."""
    page.goto("http://localhost:8080")
    page.set_default_timeout(30000)
    
    page = LoginPage(page)
    page.login("invalid@example.com", "wrongpassword")
    
    expect(page.error_message).to_be_visible()
    expect(page.dashboard).not_to_be_visible()
```

### Screenshot Capture

Screenshots are automatically captured for test evidence and saved to `screenshots/` subdirectory:

- **Entry screenshot**: Page load state
- **Step screenshots**: After each major action
- **Success screenshots**: Verification points
- **Failure screenshots**: On assertion failures

## Project Structure

```
vs-projects/
├── README.md                    # This file
├── pyproject.toml               # Project dependencies
├── main.py                      # Interactive CLI entry point
├── src/
│   ├── __init__.py             # Package marker
│   ├── llm_client.py           # Ollama API client
│   └── test_generator.py       # Test generation logic
├── generated_tests/            # Output directory for generated tests
│   ├── mock_insurance_site.html  # Mock insurance portal
│   └── test_*.py               # Generated test files
├── screenshots/                # Automatically generated screenshots
└── requirements.txt            # Python dependencies
```

### Component Details

#### `LLMClient` (`src/llm_client.py`)

Handles communication with the Ollama API:
- `__init__(model_name=None)`: Initialize with model configuration
- `generate_test(user_request, additional_context=None)`: Generate test code
- `generate_test_async(user_request)`: Async version for concurrent requests
- `_extract_code(text)`: Parse markdown code blocks from LLM response

#### `TestGenerator` (`src/test_generator.py`)

Manages test generation workflow:
- `__init__(model_name=None, output_dir="generated_tests")`: Configure generator
- `generate_and_save(user_request)`: Generate and save test file
- `_ensure_output_dir()`: Validate/write permissions for output directory
- `_cleanup_markdown_response(code)`: Remove markdown formatting from LLM output

## Mock Insurance Site

The project includes a mock insurance portal (`generated_tests/mock_insurance_site.html`) for testing:

### Features
- **Login Page**: Email and password authentication
- **Dashboard**: Shows welcome message and navigation
- **Policy Section**: View and manage insurance policies
- **Vehicle Management**: Add/remove vehicles from policies
- **Claims Section**: Submit new claims
- **Contact Form**: Simple contact page

### API Mocking Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/login` | POST | Simulate login authentication |
| `/api/policies` | GET | Return mock policy data |
| `/api/vehicles/lookup` | GET | Simulate vehicle registration lookup |
| `/api/vehicles/add` | POST | Add vehicle to policy |
| `/api/claims` | POST | Submit a claim |

## Error Handling

The tool includes comprehensive error handling:

1. **Connection Errors**: Clear message if Ollama is not running
2. **Permission Errors**: Validates output directory write access
3. **Timeout Errors**: Configurable via `OLLAMA_TIMEOUT`
4. **Empty Response**: Validates LLM returns code before saving
5. **Invalid Code**: Markdown parsing handles various response formats

## Troubleshooting

### "Could not connect to Ollama"
- Ensure Ollama is running: `ollama serve`
- Check Ollama is on port 11434 (default)
- Verify `OLLAMA_MODEL` matches an installed model: `ollama list`

### Model Not Found Error
```bash
ollama pull <model-name>
# Example:
ollama pull qwen3.5:35b
```

### Permission Denied for Output Directory
- Check write permissions in the output directory
- Specify a different `output_dir` that you have write access to
- On Windows, check folder security settings

### Timeout Issues
Increase the timeout:
```bash
export OLLAMA_TIMEOUT=120
```

### Generated Tests Don't Match Current Site
The generated tests may reference locators that need adjustment:
1. Open the generated test file
2. Use browser DevTools to inspect elements
3. Update locators to match your current application
4. Prefer semantic locators: `get_by_role`, `get_by_label`, `get_by_text`

### Screenshot Issues
- Ensure the `screenshots/` directory exists and is writable
- Check that `playwright` is installed: `pip install playwright`
- Install browser binaries: `playwright install chromium`

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `ollama` | >=0.1.0 | Python client for Ollama |
| `openai` | >=2.3.0 | OpenAI-compatible API client |
| `playwright` | >=1.40.0 | Browser automation framework |
| `pytest-playwright` | >=0.4.0 | Playwright pytest integration |
| `python-dotenv` | >=1.1.1 | Environment variable management |
| `requests` | >=2.32.5 | HTTP requests to Ollama API |

## Best Practices

### When Writing Test Descriptions

1. **Be Specific**: "Navigate to login page, enter email and password, click login button"
2. **Include Expected Outcomes**: "...and verify redirect to dashboard"
3. **Specify Edge Cases**: "Test with empty password shows validation error"
4. **Mention Data**: "Enter test@example.com and password123"

### When Updating Generated Tests

1. **Update Locators**: Use browser DevTools to find current element selectors
2. **Maintain POM Pattern**: Keep page classes separate from test functions
3. **Add Screenshots**: Insert `page.screenshot(path=...)` at key points
4. **Validate Assertions**: Ensure `expect()` assertions match actual UI states

## Future Enhancements

- [ ] Support for multiple test assertion styles
- [ ] Enhanced visual regression testing generation
- [ ] API test generation support with detailed mocking
- [ ] Test data generation and cleanup
- [ ] Batch test generation from multiple scenarios
- [ ] Support for additional frameworks (Cypress, Puppeteer)
- [ ] Test execution report generation
- [ ] Integration with CI/CD pipelines (Jenkins, GitHub Actions)
- [ ] Custom prompt templates for different testing styles

## For Job Applicants / HR Reviewers

This project demonstrates **modern QA automation skills** including:
- **AI/ML Integration**: Working with LLM APIs for code generation
- **Clean Architecture**: Modular, maintainable code structure
- **User Experience**: Interactive CLI with helpful feedback
- **Best Practices**: Page Object Model, semantic locators, async/await

### Quick Visual Overview (No Running Required)

#### What the Tool Does

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI PLAYWRIGHT TEST GENERATOR                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   User Input (Natural Language)                                     │
│   "Log in with email and password, verify dashboard appears"        │
│                            │                                        │
│                            ▼                                        │
│   ┌─────────────────────────────────────────────────────┐          │
│   │               AI TEST GENERATION ENGINE             │          │
│   │                                                     │          │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │          │
│   │  │ Prompt       │ →│ LLM API      │ →│ Cleaned  │ │          │
│   │  │ Construction │  │ (Ollama)     │  │ Code     │ │          │
│   │  └──────────────┘  └──────────────┘  └──────────┘ │          │
│   │         │                │                    │         │
│   │         └────────────────┴────────────────────┘         │          │
│   │                          │                               │          │
│   │                          ▼                               │          │
│   │              Generate Playwright Test Code               │          │
│   └─────────────────────────────────────────────────────┘          │
│                            │                                        │
│                            ▼                                        │
│                    Generated Test File                             │
│              test_YYYYMMDD_HHMMSS_description.py                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### Code Structure - Key Files

**1. `src/llm_client.py` - LLM Communication Layer**
- Handles API calls to Ollama
- Extracts code from LLM responses
- Manages timeouts and error handling

**2. `src/test_generator.py` - Test Generation Logic**
- Validates output directory permissions
- Generates timestamped test filenames
- Formats tests with Page Object Model pattern

**3. `main.py` - Interactive CLI**
- Menu-driven interface for test generation
- Mock site server integration
- Multi-mode operation (interactive, headless, server-only)

#### Sample Generated Test (from `generated_tests/`)

```python
# test_20260228_143000_changing_a_vehicle_on_a_car_insurance_policy.py
from playwright.sync_api import Page, expect

class InsuranceHomePage:
    def __init__(self, page: Page):
        self.page = page
        self.login_button = page.get_by_role("link", name="Login")
        self.my_policies_link = page.get_by_role("link", name="My Policies")
        self.sign_out_button = page.get_by_role("link", name="Sign out")
    
    def click_login(self):
        self.login_button.click()
    
    def navigate_to_policies(self):
        self.my_policies_link.click()
    
    def sign_out(self):
        self.sign_out_button.click()

class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        self.email_label = page.get_by_label("Email address")
        self.password_label = page.get_by_label("Password")
        self.sign_in_button = page.get_by_role("button", name="Sign in")
    
    def enter_credentials(self, email: str, password: str):
        self.email_label.fill(email)
        self.password_label.fill(password)

class PolicyDetailsPage:
    def __init__(self, page: Page):
        self.page = page
        self.vehicle_card = page.get_by_role("region", name="Your vehicle")
        self.change_vehicle_button = page.get_by_role("button", name="Change vehicle")
        self.registration_input = page.get_by_label("Enter registration number")
        self.look_up_button = page.get_by_role("button", name="Look up vehicle")

def test_changing_a_vehicle_on_a_car_insurance_policy(page: Page):
    """
    Scenario: Change vehicle on insurance policy
    
    Given I am on the insurance portal home page
    When I log in with valid credentials
    And I navigate to my policies and select a policy
    And I initiate a vehicle change
    Then I can enter a registration number and look up vehicle details
    """
    page.goto("http://localhost:8080")
    page.set_default_timeout(30000)
    
    # Log in
    login_page = LoginPage(page)
    login_page.enter_credentials("test@example.com", "password123")
    login_page.sign_in_button.click()
    
    # Navigate to policies
    home_page = InsuranceHomePage(page)
    home_page.navigate_to_policies()
    
    # Change vehicle
    policy_page = PolicyDetailsPage(page)
    policy_page.change_vehicle_button.click()
    policy_page.registration_input.fill("AB12 CDE")
    policy_page.look_up_button.click()
    
    # Verify vehicle lookup worked
    expect(page).to_have_url("/policy/*/vehicles")
```

#### Tech Stack Demonstrated

| Skill Area | Implementation |
|------------|----------------|
| **Python** | Type hints, async/await, pathlib, error handling |
| **API Integration** | Ollama API client, timeout management |
| **CLI Design** | Interactive menus, user input handling |
| **Code Quality** | Clean architecture, separation of concerns |
| **Web Testing** | Playwright, Page Object Model, semantic selectors |
| **File I/O** | Directory management, file creation, path handling |

#### Key Features HR Can Verify at a Glance

✅ **Interactive CLI** - Menu-driven interface with clear options  
✅ **AI Integration** - Ollama API client with proper error handling  
✅ **Modern Python** - Async/await, type hints, f-strings  
✅ **Clean Code** - Modular design, reusable components  
✅ **User Experience** - Progress indicators, clear error messages  
✅ **Test Automation** - Playwright best practices (POM, assertions)  
✅ **Mock Infrastructure** - HTML mock site with mock API endpoints  

#### What This Shows to Employers

1. **Full-Stack Capability**: Backend (API client) + Frontend (CLI interface) + Infrastructure (mock site)
2. **AI/ML Interest**: Integration with local LLMs, understanding of AI-assisted development
3. **QA Automation**: Modern testing patterns, async testing, reliable selectors
4. **Code Quality**: Structured, documented, maintainable code
5. **Problem-Solving**: Real-world test automation scenario with complete solution

### How to Use This Documentation

1. **Show README.md** - Full documentation with features, usage, and examples
2. **Show `generated_tests/`** - Example of actual generated tests
3. **Show `src/`** - Code structure and implementation
4. **Show mock site** - Demonstrate the mock insurance portal

This documentation requires **no execution** - all evidence is in the code and documentation itself.

## License

This project is provided as-is for personal and educational use.
