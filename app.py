import json, re
from fastapi import FastAPI, Request
from agent_wrapper import call_gemini, extract_generated_text

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

def build_prompt(text):
    return f"""
You are a cybersecurity log analysis agent. Read the log and return JSON ONLY in this format:

{{
  "severity": "...",
  "category": "...",
  "summary": "...",
  "root_cause": "...",
  "recommended_actions": ["...", "..."]
}}

LOG:
{text}
"""

@app.post("/agent/execute")
async def execute(request: Request):
    body = await request.json()
    text = body.get("input")
    prompt = build_prompt(text)

    gemini_resp = call_gemini(prompt)
    generated = extract_generated_text(gemini_resp)

    # extract JSON block
    try:
        m = re.search(r"\{[\s\S]*\}", generated)
        parsed = json.loads(m.group(0))
        return {"ok": True, "result": parsed}
    except:
        return {"ok": False, "raw": generated}
