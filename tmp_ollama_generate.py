import ast

from src.llm_client import LLMClient

client = LLMClient(provider_name="ollama", model="qwen3.5:27b")
print("Provider:", client.provider_name)
print("Model:", client.model)
prompt = "Generate a pytest sync Playwright test function that visits example.com and asserts the title."

try:
    code = client.generate_test(prompt)
    print("Generated code:")
    print(code)
    ast.parse(code)
    print("\nSyntax valid: True")
except Exception as e:
    print("ERROR:", type(e).__name__, e)
    import traceback

    traceback.print_exc()
