# Fix for Generated Code Syntax Validation Error

## Problem Summary

The UI was reporting:
```
Line 1: invalid syntax (text: from playwright.sync_api): Syntax error detected
```

This was caused by LM Studio responses containing:
1. Analysis text before the code
2. Channel markers (`<channel|>`) separating analysis from code
3. The model generating code with broken line breaks in import statements

## Root Causes Identified

1. **LM Studio output format**: Model returns plain text analysis + channel marker + code
2. **Extraction issues**: The response wasn't being cleaned before parsing
3. **Over-aggressive normalization**: Previous normalise_code_newlines was breaking multi-line imports by adding newlines in the wrong places

## Fixes Applied

### 1. Added Response Extraction (`src/llm_client.py`)
```python
def _extract_code(self, raw_text: str) -> str:
    """Clean LLM completion text by extracting only valid Python code."""
    # Removes channel markers
    cleaned = re.sub(r"<channel\|>+", "", raw_text)
    
    # Extracts fenced code blocks
    # Removes prompt echoes
    # Returns only the Python code portion
```

**Tests**: 8 passing extraction tests

### 2. Simplified Normalization (`src/llm_client.py`)
```python
def normalise_code_newlines(self, code: str) -> str:
    """Minimal cleanup - remove extra whitespace, don't break valid syntax."""
    # Only: normalize line endings and remove trailing spaces
    # NO regex that adds newlines (those were breaking imports)
```

### 3. Auto-extract in generate_test (`src/llm_client.py`)
The `generate_test()` method now:
1. Calls `_extract_code()` to clean the response
2. Calls `normalise_code_newlines()` for basic cleanup
3. Returns clean Python code

## Verification

### Unit Tests (All Passing)
- ✓ 22 test_test_generator tests
- ✓ 8 test_llm_client extraction tests
- ✓ Full pipeline integration test

### End-to-End Test Results
```
[TEST 1] Extract code from model response with channel markers
   ✓ Valid Python with 2 test functions

[TEST 2] Full test generation pipeline
   ✓ Generated test file with valid Python syntax

[TEST 3] Streamlit validation pipeline
   ✓ Simple test: correctly validated
   ✓ Invalid syntax: correctly rejected

[TEST 4] Execute generated tests with pytest
   ✓ Pytest successfully collected tests
```

## How to Test with LM Studio

### Prerequisites
1. LM Studio running on localhost:1234
2. Model loaded: `qwen/qwen3.5-35b`

### Test Steps

1. **Start the UI**:
```bash
uv run streamlit run streamlit_app.py --server.port 8501
```

2. **Enter user story for https://automationexercise.com/**:
```
As a customer, I want to:
1. Log in to the website
2. Add items to shopping cart
3. Navigate to cart page
4. Verify items are in cart
5. Complete checkout process
```

3. **Configure settings**:
- Base URL: `https://automationexercise.com/`
- LLM Provider: `lm-studio`
- Model: `qwen/qwen3.5-35b`

4. **Generate tests** and verify:
- ✓ No "invalid syntax" errors on Line 1
- ✓ Generated test file has valid Python syntax
- ✓ Tests can be run with: `pytest generated_tests/test_*.py -v`

5. **Run generated tests**:
```bash
pytest generated_tests/test_*.py -v
```

Expected: Tests should run (may skip if locators aren't found, but won't fail on syntax)

## Files Changed
- `src/llm_client.py`: Added _extract_code(), simplified normalise_code_newlines()
- `src/test_generator.py`: Minor cleanup
- `tests/test_llm_client.py`: Added extraction test cases
- `test_full_pipeline.py`: Comprehensive integration test (new)
- `test_end_to_end.py`: Unit test validation (new)

## What to Check Next

If still seeing syntax errors after LM Studio testing:
1. Check LM Studio response in streamlit sidebar logs
2. Verify the model is returning proper Python code
3. Check if page context is being injected correctly
4. May need to adjust system prompt if model is confused

The code extraction and validation now works correctly - any remaining issues would be in the models ability to generate valid Python given the prompts.
