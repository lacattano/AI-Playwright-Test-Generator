# AI-Playwright-Test-Generator

An AI-powered tool that generates Playwright Python test scripts using local LLM models via Ollama.

| Metric | Status |
|--------|--------|
| CI/CD Pipeline | [![CI](https://github.com/lacattano/AI-Playwright-Test-Generator/actions/workflows/ci.yml/badge.svg)](https://github.com/lacattano/AI-Playwright-Test-Generator/actions) |
| Python Version | ![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg) |
| License | ![License](https://img.shields.io/badge/license-MIT-green.svg) |
| Code Coverage | [![codecov](https://codecov.io/gh/lacattano/AI-Playwright-Test-Generator/branch/main/graph/badge.svg)](https://codecov.io/gh/lacattano/AI-Playwright-Test-Generator) |
| Code Quality | [![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) |

---

## What This Shows to Employers

This project demonstrates **modern QA automation and AI integration skills**:

| Skill Area | Implementation |
|------------|----------------|
| **AI/ML Integration** | Ollama LLM API client with error handling and timeouts |
| **Modern Python** | Type hints, dataclasses, pathlib, f-strings |
| **Clean Architecture** | Modular design, separation of concerns |
| **CLI Development** | argparse-based CLI with subcommands and structured output |
| **Web Testing** | Playwright, Page Object Model, semantic selectors |
| **API Integration** | HTTP clients, timeout management, JSON parsing |
| **Infrastructure** | Docker support, mock site with simulated APIs |
| **Documentation** | Comprehensive README with examples and troubleshooting |

### Key Features at a Glance

✅ **AI-Powered** - Generates tests from natural language descriptions  
✅ **Local LLM** - Runs entirely locally using Ollama (no API costs)  
✅ **Modern Tests** - pytest sync Playwright with Page Object Model  
✅ **Docker Support** - Consistent, reproducible test environments  
✅ **Mock Infrastructure** - Built-in insurance portal for testing  
✅ **Screenshot Capture** - Automated test evidence collection  
✅ **CLI Tool** - Command-line interface with multiple output formats  
✅ **Multi-Format Reports** - Jira, HTML, Markdown, JSON, XML exports  
✅ **Pre-commit Hooks** - Automated linting and formatting with ruff  

---

## Features

- **AI-Powered Test Generation**: Generate Playwright tests from simple text descriptions
- **Local LLM Support**: Runs entirely locally using Ollama (no API costs or data privacy concerns)
- **Pytest Test Generation**: Creates pytest sync Playwright tests with screenshot capture
- **Page Object Model (POM)**: Generated tests follow POM pattern with reusable page classes
- **Mock Site Generation**: Includes a built-in mock insurance website for testing against
- **Flexible Configuration**: Supports multiple LLM models with environment variables
- **Robust Error Handling**: Validates permissions and provides clear error messages
- **CLI Interface**: Command-line interface with subcommands (`generate`, `test`, `help`)
- **Multi-Format Output**: Generate reports in Jira, HTML, Markdown, JSON, and XML formats

---

## Prerequisites

**Option 1: Run Locally**

1. **Python 3.13+**: This project requires Python 3.13 or higher
2. **Ollama**: Download from https://ollama.com
3. **Ollama Model**: `ollama pull qwen3.5:35b`

**Option 2: Run with Docker**

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed

---

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd AI-Playwright-Test-Generator
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Install dependencies**:
   ```bash
   uv sync
   # or
   # Note: use uv, not pip
   playwright install chromium
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | The Ollama model to use | `qwen3.5:35b` |
| `OLLAMA_TIMEOUT` | Request timeout in seconds | `300` |

**Set environment variables:**

**Windows (PowerShell):**
```powershell
$env:OLLAMA_MODEL="qwen3.5:35b"
$env:OLLAMA_TIMEOUT="300"
```

**Windows (Command Prompt):**
```cmd
set OLLAMA_MODEL=qwen3.5:35b
set OLLAMA_TIMEOUT=300
```

**Linux/macOS:**
```bash
export OLLAMA_MODEL=qwen3.5:35b
export OLLAMA_TIMEOUT=300
```

---

## Quick Start — Streamlit UI (Recommended)

The primary interface is a Streamlit web app for non-technical QA testers.

```bash
# Launch UI only (use your own target site)
bash launch_ui.sh

# Launch UI + mock insurance site (development/demo)
bash launch_dev.sh
```

Then open http://localhost:8501 in your browser.

**Workflow:**
1. Enter a user story or acceptance criteria
2. Set the base URL of the site to test
3. Click **✨ Generate Test** — the scraper visits the URL and injects real selectors
4. Review the coverage analysis
5. Click **▶️ Run Now** to execute the test
6. Download reports in Python, JSON, HTML, or Jira format

---

## CLI Usage

### Quick Start - Interactive Mode

```bash
$env:OLLAMA_MODEL="qwen3.5:35b"
python main.py
```

**Options:**
1. Generate Playwright test (standard mode)
2. Generate test with auto-open mock site
3. Start mock server only
4. Generate test (headless, no UI)
5. Exit

**Enter your test scenario** when prompted:
```
Enter the feature to test: Log in to the site with email and password
```

### CLI Mode - Generate Command

**Generate test from text:**
```bash
python -m cli.main generate --input "As a user, I want to log in with email and password"
```

**Generate from file:**
```bash
python -m cli.main generate --file user_stories.txt --mode thorough
```

**Generate from JSON:**
```bash
python -m cli.main generate --file test_cases.json --format json
```

**Generate with custom output:**
```bash
python -m cli.main generate --input "Login feature" --output ./my_tests --mode fast
```

**Generate all report types:**
```bash
python -m cli.main generate --input "Checkout flow" --reports all
```

### CLI Commands Reference

#### `generate` - Generate Playwright tests

```bash
python -m cli.main generate [options]
```

**Options:**

| Flag | Short | Description | Default | Choices |
|------|-------|-------------|---------|---------|
| `--input` | `-i` | Raw test case input | - | - |
| `--file` | `-f` | Input file (text or JSON) | - | - |
| `--generate` | `-g` | Generate test case from prompt | - | - |
| `--format` | | Input format | `user_story` | `user_story`, `gherkin`, `auto` |
| `--output` | `-o` | Output directory | `generated_tests` | - |
| `--mode` | | Analysis mode | `fast` | `fast`, `thorough`, `auto` |
| `--project-key` | | Jira project key | `TEST` | - |
| `--evidence` | | Generate evidence files | `true` | - |
| `--reports` | | Report format | `all` | `all`, `jira`, `html`, `json`, `md` |

#### `test` - Run test suite

```bash
python -m cli.main test [options]
```

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--filter` | `-f` | Test filter pattern |

#### `help` - Show help message

```bash
python -m cli.main help
```

### Report Formats

The CLI generates multiple report formats automatically:

| Format | Description | Output File |
|--------|-------------|-------------|
| `jira` | Jira-compatible test case format | `test_report_JIRA.txt` |
| `html` | Visual HTML report with formatting | `test_report_YYYYMMDD_HHMMSS.html` |
| `markdown` | Markdown documentation | `test_report_YYYYMMDD_HHMMSS.md` |
| `json` | Machine-readable JSON format | `test_cases_YYYYMMDD_HHMMSS.json` |
| `xml` | XML format for CI/CD integration | `test_cases_YYYYMMDD_HHMMSS.xml` |

### Example JSON Report

```json
{
  "test_cases": [
    {
      "id": "TEST-1",
      "title": "User login with valid credentials",
      "description": "As a user, I want to log in to the system...",
      "complexity": "LOW",
      "steps": [
        "Navigate to login page",
        "Enter email and password",
        "Click login button"
      ],
      "expected_results": [
        "User is redirected to dashboard",
        "Welcome message is displayed"
      ]
    }
  ],
  "metadata": {
    "generated_at": "2026-03-03T22:27:04",
    "analysis_mode": "fast"
  }
}
```

---

## Running Generated Tests

```bash
# Run a specific generated test
pytest generated_tests/test_20260307_141729_my_test.py -v

# Run with headed browser (see the browser)
pytest generated_tests/test_my_test.py --headed -v

# Run all unit tests for the tool itself
pytest tests/ -v
```

> **Note:** Generated tests require the target site to be running.
> Use `bash launch_dev.sh` to start the mock site before running generated tests.

---

## Project Structure

```
AI-Playwright-Test-Generator/
├── streamlit_app.py             # Streamlit UI (primary entry point)
├── main.py                      # Interactive CLI entry point
├── launch_ui.sh                 # Launch Streamlit UI only
├── launch_dev.sh                # Launch UI + mock insurance site
├── pyproject.toml               # Project dependencies (managed by uv)
├── pytest.ini                   # Pytest configuration
├── cli/                         # CLI module
│   ├── main.py
│   ├── config.py
│   ├── input_parser.py
│   ├── story_analyzer.py
│   ├── test_orchestrator.py
│   ├── evidence_generator.py
│   └── report_generator.py
├── src/                         # Core modules
│   ├── llm_client.py            # ✅ PROTECTED — Ollama API client
│   ├── test_generator.py        # ✅ PROTECTED — Test generation logic
│   ├── file_utils.py            # Save, rename, normalise helpers
│   └── page_context_scraper.py  # DOM scraper for real locator injection
├── tests/                       # Unit tests for the tool itself
├── generated_tests/             # Output: tests produced BY the tool
│   └── mock_insurance_site.html # Mock test environment
├── screenshots/                 # Screenshot evidence
├── docs/                        # Implementation specs
└── .pre-commit-config.yaml      # ruff + ruff-format + mypy hooks
```

### CLI Module Components

| Module | Purpose |
|--------|---------|
| `main.py` | CLI entry point with argparse command handling |
| `config.py` | Configuration classes: `AnalysisMode`, `ReportFormat` |
| `input_parser.py` | Parse user stories, Gherkin, or JSON input to test cases |
| `story_analyzer.py` | Analyze test cases for complexity and Jira metadata |
| `test_orchestrator.py` | Orchestrates test code generation from analyzed cases |
| `evidence_generator.py` | Generates test evidence files (screenshots, logs) |
| `report_generator.py` | Creates reports in multiple formats (Jira, HTML, Markdown, JSON) |

### Configuration Classes

**AnalysisMode** - Analysis depth for test generation:

| Value | Description |
|-------|-------------|
| `fast` | Quick analysis, minimal context |
| `thorough` | Detailed analysis, comprehensive context |
| `auto` | Auto-detect optimal mode |

**ReportFormat** - Output format for reports:

| Value | Description |
|-------|-------------|
| `JIRA` | Jira-compatible format |
| `HTML` | Visual HTML report |
| `MARKDOWN` | Markdown documentation |
| `JSON` | Machine-readable JSON |
| `XML` | XML for CI/CD integration |

---

## Pre-commit Configuration

To install and run pre-commit hooks:

```bash
# Install pre-commit hooks
pre-commit install

# Run pre-commit on all files
pre-commit run --all-files

# Run pre-commit on changed files only
pre-commit run
```

**Configuration:**

- **Ruff** - Python linting with auto-fix support
- **Ruff-Format** - Consistent code formatting
- **Mypy** - Python type checking
- **Excluded directories** - `generated_tests/` is excluded from checks

---

## Mock Insurance Site Features

- Login page with email/password authentication
- Dashboard with welcome message and navigation
- Policy management section
- Vehicle lookup and management
- Claims submission form

**Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/login` | POST | Simulate login |
| `/api/policies` | GET | Return mock policies |
| `/api/vehicles/lookup` | GET | Vehicle lookup |
| `/api/claims` | POST | Submit claims |

---

## Docker Support

### Quick Start

```bash
docker-compose up --build
```

**Services:**
| Service | URL | Description |
|---------|-----|-------------|
| `ollama` | `http://localhost:11434` | LLM serving endpoint |
| `test-generator` | `http://localhost:8080` | Mock site server |

**Generate tests in container:**
```bash
docker-compose exec test-generator python -m cli.main generate --input "Login feature"
```

**Common commands:**
```bash
docker-compose up -d              # Start in background
docker-compose logs -f            # View logs
docker-compose exec test-generator bash  # Open shell
docker-compose down               # Stop containers
```

---

## Troubleshooting

### "Could not connect to Ollama"
```bash
ollama serve
ollama list  # Verify model is installed
ollama pull qwen3.5:35b
```

### Timeout Issues
```bash
export OLLAMA_TIMEOUT=300
```

### Generated Tests Need Locator Updates
1. Open DevTools to inspect elements
2. Update locators to match current application
3. Prefer semantic selectors: `get_by_role`, `get_by_label`

### Invalid JSON Input
Ensure your JSON file follows the expected format:
```json
{
  "test_cases": [
    {
      "title": "Test title",
      "description": "Test description",
      "complexity": "LOW",
      "priority": 1
    }
  ]
}
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `ollama` | Python client for Ollama |
| `openai` | OpenAI-compatible API client |
| `playwright` | Browser automation |
| `pytest-playwright` | Test framework integration |
| `python-dotenv` | Environment variables |
| `requests` | HTTP requests |

---

## Future Enhancements

- [x] Multiple test assertion styles
- [x] Visual regression testing
- [x] API test generation with mocking
- [x] Batch test generation
- [x] Cypress/Puppeteer support
- [x] CI/CD pipeline integration
- [x] Pre-commit hooks with ruff
- [ ] Enhanced LLM prompt templates
- [ ] Test case parameterization
- [ ] Data-driven test generation
- [ ] Integration with test management tools (Jira, Xray)

---

**License**: This project is provided as-is for personal and educational use.