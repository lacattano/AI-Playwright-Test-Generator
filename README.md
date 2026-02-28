# Playwright Test Generator

An AI-powered tool that generates Playwright Python test scripts using local LLM models via Ollama. This project helps automate the creation of modern, async Playwright tests based on natural language descriptions.

## Features

- **AI-Powered Test Generation**: Generate Playwright tests from simple text descriptions
- **Local LLM Support**: Runs entirely locally using Ollama (no API costs or data privacy concerns)
- **Async Test Generation**: Creates modern async/await Playwright tests by default
- **Flexible Configuration**: Supports multiple LLM models with environment variable configuration
- **Robust Error Handling**: Validates permissions and provides clear error messages
- **Customizable Output**: Save generated tests to a configurable output directory

## Prerequisites

1. **Python 3.13+**: This project requires Python 3.13 or higher
2. **Ollama**: A local LLM server that runs various models
   - Download from: https://ollama.com
   - Install Ollama on your system
3. **Ollama Model**: Download a compatible model (e.g., `qwen3.5:35b`)
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

You can configure the tool using the following environment variables:

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `OLLAMA_MODEL` | The Ollama model to use for test generation | `qwen3.5:35b` | `qwen2.5:7b` |
| `OLLAMA_TIMEOUT` | Request timeout in seconds | `60` | `120` |

To set environment variables:

**Windows (Command Prompt):**
```cmd
set OLLAMA_MODEL=qwen2.5:7b
set OLLAMA_TIMEOUT=120
```

**Windows (PowerShell):**
```powershell
$env:OLLAMA_MODEL="qwen2.5:7b"
$env:OLLAMA_TIMEOUT="120"
```

**Linux/macOS:**
```bash
export OLLAMA_MODEL=qwen2.5:7b
export OLLAMA_TIMEOUT=120
```

## Usage

### Quick Start - Command Line

The easiest way to use this project is to run the `main.py` script:

1. **Make sure Ollama is running** (in a separate terminal):
   ```bash
   ollama serve
   ```

2. **Set the model and run the generator**:
   ```bash
   # Windows PowerShell
   $env:OLLAMA_MODEL="qwen3.5:35b"
   python main.py
   ```

3. **Enter your test scenario** when prompted:
   ```
   Enter test scenario description: Log in to example.com with email and password
   ```

4. **The test will be saved** to `generated_tests/` with a timestamped filename.

### Quick Start - Python Script

You can also use the generator programmatically in your own Python scripts:

```python
from src.test_generator import TestGenerator

# Initialize the generator (uses default model and output directory)
generator = TestGenerator()

# Generate a test
user_request = "Go to google.com and search for playwright"
file_path = generator.generate_and_save(user_request)

print(f"Test saved to: {file_path}")
```

### Custom Model

Specify a different Ollama model via environment variable or parameter:

**Via Environment Variable:**
```bash
$env:OLLAMA_MODEL="qwen2.5:7b"
python main.py
```

**Via Python Code:**
```python
generator = TestGenerator(model_name="qwen2.5:7b")
```

### Custom Output Directory

Save tests to a specific directory:

```python
generator = TestGenerator(output_dir="my_tests")
```

### Advanced Usage

Run from command line with custom settings:

```bash
# Set model and timeout
$env:OLLAMA_MODEL="qwen2.5:7b"
$env:OLLAMA_TIMEOUT="120"

# Run the generator
python main.py
```

### Interactive Examples

**Example 1: Simple Search**
```
Enter test scenario description: Go to google.com and search for playwright
```

**Example 2: Login Test**
```
Enter test scenario description: Navigate to example.com/login, enter email test@example.com and password secret123, click login button, verify redirect to dashboard
```

**Example 3: E-commerce Flow**
```
Enter test scenario description: Go to amazon.com, search for "laptop", filter by 4+ stars, click first result, verify product page title contains "laptop"
```

## Output Format

The generated tests follow these conventions:

- **Filename Format**: `test_YYYYMMDD_HHMMSS_<description>.py`
- **Code Style**: Modern async/await Playwright tests
- **Imports**: Uses `async_playwright` for async support
- **Comments**: Includes explanatory comments
- **Selectors**: Uses semantic selectors (data-testid, CSS, XPath)
- **Wait Handling**: Implicit waits with explicit fallback for dynamic content

### Example Output

```python
# test_20260228_143000_Go to google.py
from playwright.async_api import async_playwright, Page

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigate to Google
        await page.goto("https://www.google.com")
        
        # Search for Playwright
        await page.fill("input[name='q']", "playwright")
        await page.click("input[name='btnK']")
        
        # Verify search results
        await page.wait_for_selector("div[jsname]")
        print("Search completed successfully!")
        
        await browser.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Project Structure

```
vs-projects/
├── README.md              # This file
├── pyproject.toml         # Project dependencies
├── main.py               # Entry point example
├── src/
│   ├── __init__.py       # Package marker
│   ├── llm_client.py     # Ollama API client
│   └── test_generator.py # Test generation logic
└── generated_tests/      # Output directory for generated tests
```

## Component Details

### `LLMClient` (`src/llm_client.py`)

Handles communication with the Ollama API:
- `__init__(model_name=None)`: Initialize with model configuration
- `generate_test(user_request, additional_context=None)`: Generate test code
- `_extract_code(text)`: Parse markdown code blocks from LLM response

### `TestGenerator` (`src/test_generator.py`)

Manages test generation workflow:
- `__init__(model_name=None, output_dir="generated_tests")`: Configure generator
- `generate_and_save(user_request)`: Generate and save test file
- `_ensure_output_dir()`: Validate/write permissions for output directory

## Error Handling

The tool includes comprehensive error handling:

1. **Connection Errors**: Clear message if Ollama is not running
2. **Permission Errors**: Validates output directory write access
3. **Timeout Errors**: Configurable via `OLLAMA_TIMEOUT`
4. **Empty Response**: Validates LLM returns code before saving

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

### Timeout Issues
Increase the timeout:
```bash
export OLLAMA_TIMEOUT=120
```

## Dependencies

- `openai>=2.3.0` - For OpenAI-compatible API client
- `playwright>=1.40.0` - Playwright browser automation
- `pytest-playwright>=0.4.0` - Playwright test integration
- `python-dotenv>=1.1.1` - Environment variable management
- `requests>=2.32.5` - HTTP requests to Ollama API
- `ollama>=0.1.0` - Python client for Ollama

## Future Enhancements

- [ ] Support for multiple test assertion styles
- [ ] Visual regression testing generation
- [ ] API test generation support
- [ ] Test data generation integration
- [ ] Batch test generation from multiple scenarios
- [ ] Support for additional frameworks (Cypress, Puppeteer)

## License

This project is provided as-is for personal and educational use.

## Contributing

Feel free to fork this repository and submit pull requests for improvements.