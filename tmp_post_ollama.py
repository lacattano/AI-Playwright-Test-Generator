import httpx

url = "http://127.0.0.1:11434/api/chat"
json = {"model": "qwen3.5:27b", "messages": [{"role": "user", "content": "Hello"}], "stream": False}
try:
    r = httpx.post(url, json=json, timeout=10)
    print("STATUS", r.status_code)
    print(r.text[:2000])
except Exception as e:
    print(type(e).__name__, e)
