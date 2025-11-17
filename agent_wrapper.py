import os
import requests
import json

API_KEY = os.getenv("GEMINI_API_KEY")

# High availability model
MODEL = "models/gemini-2.0-flash-001"
API_URL = f"https://generativelanguage.googleapis.com/v1/{MODEL}:generateContent?key={API_KEY}"

def call_gemini(prompt):
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    resp = requests.post(API_URL, json=body, headers=headers)

    if not resp.ok:
        return {"error": True, "status": resp.status_code, "body": resp.text}

    return resp.json()

def extract_generated_text(resp):
    try:
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return json.dumps(resp)
