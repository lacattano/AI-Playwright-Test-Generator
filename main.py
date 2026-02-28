# src/main.py
import re
from ollama import chat  # Ensure you have ollama installed: pip install ollama

# Initialize the client (implicitly used via the chat function in python-ollama)
# If you need explicit client management, you can do:
# from ollama import Client
# client = Client(host="http://localhost:11434")

def slugify(text):
    """Convert feature name to a valid Python variable name."""
    slug = re.sub(r'[^a-zA-Z0-9]', '_', text)
    return slug.lower()

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
            model="qwen3.5:35b", # Make sure this model is pulled: ollama pull qwen3.5:35b
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        # Extract the content from the response
        return response['message']['content']
    except Exception as e:
        return f"Error generating Playwright tests: {e}"

def main():
    print("🤖 Welcome to the AI Playwright Test Generator!")
    print("This tool generates Playwright test scripts using Qwen3.5.")
    
    user_input = input("\nEnter the feature to test (e.g., 'User Login', 'Checkout Process'): ")
    
    if not user_input.strip():
        print("❌ Input cannot be empty.")
        return

    print("\n🧠 Generating tests based on your description...")
    
    generated_code = generate_playwright_tests(user_input)
    
    print("\n" + "="*40)
    print("📄 Generated Playwright Test Code")
    print("="*40)
    print(generated_code)
    print("="*40)
    
    print("\n💡 Next Steps:")
    print("1. Copy the code above into a file named 'test_<feature>.py'.")
    print("2. Run `pytest test_<feature>.py` to execute the tests.")
    print("3. Review the locators to ensure they match your current application.")

if __name__ == "__main__":
    main()