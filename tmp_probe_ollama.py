import httpx

paths = ["/api/chat", "/api/v1/chat", "/api/completions", "/api/v1/completions", "/api/models", "/api/v1/models"]
for path in paths:
    try:
        r = httpx.get("http://127.0.0.1:11434" + path, timeout=5)
        print(path, r.status_code)
        print(r.text[:200])
    except Exception as e:
        print(path, type(e).__name__, e)
