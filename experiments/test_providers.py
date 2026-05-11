#!/usr/bin/env python3
"""Quick test of LLM provider connectivity."""
import os
import sys
import warnings

# SSL workarounds for corporate proxy
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

print("=" * 50)
print("LLM Provider Connectivity Test")
print("=" * 50)

# Test 1: Groq
print("\n[1] Testing Groq API...")
try:
    import httpx
    from groq import Groq
    client = Groq(
        api_key=os.getenv("GROQ_API_KEY"),
        http_client=httpx.Client(verify=False)
    )
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": 'Reply JSON: {"status":"ok"}'}],
        temperature=0.1,
        max_tokens=20,
        response_format={"type": "json_object"}
    )
    print(f"    Groq OK: {resp.choices[0].message.content}")
except Exception as e:
    print(f"    Groq FAILED: {e}")

# Test 2: Gemini
print("\n[2] Testing Gemini API...")
try:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content(
        'Reply JSON: {"status":"ok"}',
        generation_config={
            "temperature": 0.1,
            "max_output_tokens": 20,
            "response_mime_type": "application/json"
        }
    )
    print(f"    Gemini OK: {resp.text}")
except Exception as e:
    print(f"    Gemini FAILED: {e}")

# Test 3: Ollama
print("\n[3] Testing Ollama...")
try:
    import httpx as hx
    r = hx.get("http://localhost:11434/api/tags", timeout=3)
    models = [m["name"] for m in r.json().get("models", [])]
    print(f"    Ollama running, models: {models if models else 'none installed'}")
except Exception as e:
    print(f"    Ollama FAILED: {e}")

print("\n" + "=" * 50)
print("Test complete.")
