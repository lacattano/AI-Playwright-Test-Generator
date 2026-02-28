# src/main.py
import re
import os
import datetime
from pathlib import Path
from typing import Optional
from ollama import chat  # Ensure you have ollama installed: pip install ollama

# Use OLLAMA_MODEL env var or default to 'qwen3.5:35b'
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:35b")

# Generated tests directory
GENERATED_TESTS_DIR = Path(__file__).parent.parent / "generated_tests"

# Initialize the client (implicitly used via the chat function in python-ollama)
# If you need explicit client management, you can do:
# from ollama import Client
# client = Client(host="http://localhost:11434")

def slugify(text: str, max_length: int = 100) -> str:
    """Convert feature name to a valid Python variable name, truncated to max_length.
    
    Windows has a 255 character filename limit, so we truncate to prevent
    OSError: [Errno 22] Invalid argument on long filenames.
    """
    slug = re.sub(r'[^a-zA-Z0-9]', '_', text)
    slug = slug.strip('_')
    slug = slug.lower()
    
    # Truncate to max_length to avoid Windows filename length issues
    if len(slug) > max_length:
        slug = slug[:max_length]
    
    return slug

def save_generated_test(feature_name: str, code: str, base_dir: Path) -> Optional[Path]:
    """Save generated test code to a file with proper naming and overwrite handling.
    
    Returns the saved file path, or None if the user cancelled.
    """
    slug = slugify(feature_name)
    test_filename = f"test_{slug}.py"
    target_path = base_dir / test_filename
    
    # Handle existing files
    counter = 1
    while target_path.exists():
        print(f"\n⚠️  {test_filename} already exists!")
        choice = input(f"Options: [1] Overwrite, [2] Rename to test_{slug}_{counter}.py, [3] Cancel: ").strip()
        
        if choice == "1":
            break
        elif choice == "2":
            test_filename = f"test_{slug}_{counter}.py"
            target_path = base_dir / test_filename
            counter += 1
        elif choice == "3":
            print("❌ File save cancelled.")
            return None
    
    # Create directory if it doesn't exist
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Write the file
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(f"# Auto-generated test for: {feature_name}\n")
        f.write(f"# Generated on: {datetime.datetime.now()}\n")
        f.write("#\n")
        f.write("# The locators in this test may need to be adjusted to match your current application.\n\n")
        f.write(code)
    
    print(f"\n✅ File saved to: {target_path.absolute()}")
    return target_path

def generate_playwright_tests(feature_name: str) -> str:
    slugified = slugify(feature_name)
    
    prompt = f"""
    You are a Senior QA Automation Engineer and an expert in Playwright.
    Your task is to generate robust, production-ready Playwright test cases in Python using the `playwright.sync_api` module.
    
    The feature description is:
    <feature>
    {feature_name}
    </feature>

    Requirements for the generated code:
    1. Use `from playwright.sync_api import Page, expect` imports.
    2. Follow the Page Object Model (POM) pattern or clear, standalone test functions.
    3. Include:
       - A test function named 'test_{slugified}' (e.g., test_user_login).
       - Robust locators (e.g., `get_by_label`, `get_by_role`, `get_by_text`) instead of fragile XPaths.
       - Assertions using `expect().to_be_visible()`, `expect().to_have_text()`, etc.
       - Edge cases: Empty fields, invalid data, network errors, and timeout handling.
    4. The code must be copy-paste ready to run in a standard Playwright test suite.
    5. Output ONLY the Python code block, no conversational filler.
    """

    try:
        # Using python-ollama's chat function directly
        response = chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        # Extract the content from the response
        code = response['message']['content']
        
        # Clean up markdown code fences and conversational filler
        lines = code.split('\n')
        cleaned_lines = []
        inside_code_block = False
        
        for line in lines:
            # Skip markdown code fence indicators
            if line.strip() in ['```python', '```', '``']:
                inside_code_block = not inside_code_block
                continue
            # Skip lines that are part of conversational filler before/after code
            stripped = line.strip()
            if not inside_code_block and stripped:
                # Look for code-like content
                if stripped.startswith('def test_') or stripped.startswith('from ') or stripped.startswith('import ') or stripped == '"""':
                    inside_code_block = True
                    cleaned_lines.append(line)
            elif inside_code_block:
                cleaned_lines.append(line)
        
        # Join and strip extra whitespace
        code = '\n'.join(cleaned_lines).strip()
        
        # Remove any remaining ``` at the end
        code = re.sub(r'`{2,3}$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^`{2,3}', '', code, flags=re.MULTILINE)
        
        return code
    except Exception as e:
        return f"Error generating Playwright tests: {e}"

def main():
    print(f"🤖 Welcome to the AI Playwright Test Generator!")
    print(f"This tool generates Playwright test scripts using {OLLAMA_MODEL}.")
    print(f"Set OLLAMA_MODEL env var to use a different model.")
    print(f"Tests will be saved to: {GENERATED_TESTS_DIR.absolute()}")
    
    user_input = input("\nEnter the feature to test (e.g., 'User Login', 'Checkout Process'): ")
    
    if not user_input.strip():
        print("❌ Input cannot be empty.")
        return

    print(f"\n🧠 Generating tests with {OLLAMA_MODEL}...")
    
    generated_code = generate_playwright_tests(user_input)
    
    print("\n" + "="*40)
    print("📄 Generated Playwright Test Code")
    print("="*40)
    print(generated_code)
    print("="*40)
    
    # Save to file automatically
    saved_file = save_generated_test(user_input, generated_code, GENERATED_TESTS_DIR)
    
    if saved_file:
        print("\n" + "="*40)
        print("📋 Generated Test Options")
        print("="*40)
        print("[1] Save to file and run pytest")
        print("[2] Save to file only")
        print("[3] Display test command only")
        print("[4] Generate another test")
        print("[5] Exit")
        print("="*40)
        
        while True:
            choice = input("\nChoose an option: ").strip()
            
            if choice == "1":
                print(f"\n🧪 Running pytest on {saved_file}...")
                os.system(f"pytest {saved_file}")
                break
            elif choice == "2":
                print(f"\n✅ Test saved successfully!")
                print(f"Run with: pytest {saved_file}")
                break
            elif choice == "3":
                print(f"\n🧪 To run this test, execute: pytest {saved_file}")
                break
            elif choice == "4":
                main()
                return
            elif choice == "5":
                print("👋 Goodbye!")
                return
            else:
                print("❌ Invalid option. Please choose 1-5.")
    else:
        print("\n💡 To run this test, save the code to 'test_<feature>.py' and execute: pytest test_<feature>.py")

if __name__ == "__main__":
    main()
