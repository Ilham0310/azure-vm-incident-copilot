#!/usr/bin/env python3
"""Quick test: verify Ollama llama3.1:8b is available and responds."""
import os, ssl, sys, urllib3
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

import requests, time

base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

print(f"Testing Ollama at {base} with model {model}")

try:
    r = requests.get(f"{base}/api/tags", timeout=5)
    models = [m["name"] for m in r.json().get("models", [])]
    print(f"Available models: {models}")
except Exception as e:
    print(f"Ollama not reachable: {e}"); sys.exit(1)

print(f"\nTesting generation (may take 60-120s on first load)...")
t0 = time.time()
try:
    r = requests.post(f"{base}/api/chat", json={
        "model": model,
        "messages": [{"role": "user", "content": 'Reply with valid JSON only: {"status": "ok"}'}],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 50}
    }, timeout=180)
    dt = time.time() - t0
    content = r.json().get("message", {}).get("content", "")
    print(f"Response ({dt:.1f}s): {content[:200]}")
    print("Ollama OK")
except Exception as e:
    print(f"Generation failed after {time.time()-t0:.0f}s: {e}")
