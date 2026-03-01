# AI Playwright Test Generator

An AI-powered tool that generates Playwright Python test scripts using local LLM models via Ollama.

## Status

| Metric | Status |
|--------|--------|
| CI/CD Pipeline | [![CI/CD Pipeline](https://github.com/lacattano/vs-projects/actions/workflows/ci.yml/badge.svg)](https://github.com/lacattano/vs-projects/actions) |
| Python 3.13 | ![Python 3.13](https://img.shields.io/badge/python-3.13+-blue.svg) |
| License | ![License](https://img.shields.io/badge/license-MIT-green.svg) |
| Test Coverage | [![Coverage Status](coverage.svg)](coverage.html) |

---

## What This Shows to Employers

This project demonstrates **modern QA automation and AI integration skills**:

| Skill Area | Implementation |
|------------|----------------|
| **AI/ML Integration** | Ollama LLM API client with error handling and timeouts |
| **Modern Python** | Type hints, async/await, pathlib, f-strings |
| **Clean Architecture** | Modular design (LLMClient, TestGenerator), separation of concerns |
| **CLI Development** | Interactive menu-driven interface with progress indicators |
| **Web Testing** | Playwright, Page Object Model, semantic selectors |
| **API Integration** | HTTP clients, timeout management, JSON parsing |
| **Infrastructure** | Docker support, mock site with simulated APIs |
| **Documentation** | Comprehensive README with examples and troubleshooting |

### Key Features at a Glance

✅ **AI-Powered** - Generates tests from natural language descriptions  
✅ **Local LLM** - Runs entirely locally using Ollama (no API costs)  
✅ **Modern Tests** - Async/await Playwright with Page Object Model  
✅ **Docker Support** - Consistent, reproducible test environments  
✅ **Mock Infrastructure** - Built-in insurance portal for testing  
✅ **Screenshot Capture** - Automated test evidence collection  

---

## Features

- **AI-Powered Test Generation**: Generate Playwright tests from simple text descriptions
- **Local LLM Support**: Runs entirely locally using Ollama (no API costs or data privacy concerns)
- **Async Test Generation**: Creates modern async/await Playwright tests with screenshot capture
- **Page Object Model (POM)**: Generated tests follow POM pattern with reusable page classes
- **Mock Site Generation**: Includes a built-in mock insurance website for testing against
- **Flexible Configuration**: Supports multiple LLM models with environment variables
- **Robust Error Handling**: Validates permissions and provides clear error messages

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
   cd vs-projects
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   # or
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Ensure Ollama is running** (for local mode):
   ```bash
   ollama serve
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | The Ollama model to use | `qwen3.5:35b` |
| `OLLAMA_TIMEOUT` | Request timeout in seconds | `60` |

**Set environment variables:**

**Windows (PowerShell):**
```powershell
$env:OLLAMA_MODEL="qwen3.5:35b"
$env:OLLAMA_TIMEOUT="120"
```

**Windows (Command Prompt):**
```cmd
set OLLAMA_MODEL=qwen3.5:35b
set OLLAMA_TIMEOUT=120
```

**Linux/macOS:**
```bash
export OLLAMA_MODEL=qwen3.5:35b
export OLLAMA_TIMEOUT=120
```

---

## Usage

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

### Programmatic Usage

```python
from src.test_generator import TestGenerator

generator = TestGenerator()
file_path = generator.generate_and_save("Log in and add a vehicle to policy")
print(f"Test saved to: {file_path}")
```

### Running Generated Tests

```bash
# Run a specific test
python generated_tests/test_20260301_143000_login_feature.py

# Run with Playwright
playwright test generated_tests/ --screenshot=on
```

---

## Project Structure

```
vs-projects/
├── README.md                    # This file
├── pyproject.toml               # Project dependencies
├── main.py                      # Interactive CLI entry point
├── src/
│   ├── __init__.py
│   ├── llm_client.py           # Ollama API client
│   └── test_generator.py       # Test generation logic
├── generated_tests/            # Generated test files & mock site
├── screenshots/                # Screenshot evidence
└── requirements.txt
```

### Mock Insurance Site Features

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
docker-compose exec test-generator python main.py
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
export OLLAMA_TIMEOUT=120
```

### Generated Tests Need Locator Updates
1. Open DevTools to inspect elements
2. Update locators to match current application
3. Prefer semantic selectors: `get_by_role`, `get_by_label`

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

- [ ] Multiple test assertion styles
- [ ] Visual regression testing
- [ ] API test generation with mocking
- [ ] Batch test generation
- [ ] Cypress/Puppeteer support
- [ ] CI/CD pipeline integration

---

**License**: This project is provided as-is for personal and educational use.