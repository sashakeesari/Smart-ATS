# lib/llm.py
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GENAI_KEY = os.getenv("GOOGLE_API_KEY")
if GENAI_KEY:
    genai.configure(api_key=GENAI_KEY)

MODEL = genai.GenerativeModel('models/gemini-1.5-flash')

# IMPORTANT: double the braces {{ }} so .format() doesn't treat them as placeholders
PROMPT = (
    "You are an experienced ATS. Evaluate the candidate resume against the given job description. "
    "Return ONLY valid minified JSON with EXACT keys: "
    "{{\"JD Match\":\"<percent 0-100 as number or string>\",\"MissingKeywords\":[...],\"Profile Summary\":\"...\"}} "
    "No extra text.\n\nresume: {resume_text}\n\ndescription: {jd_text}"
)

def call_gemini(resume_text: str, jd_text: str) -> dict:
    prompt = PROMPT.format(resume_text=resume_text, jd_text=jd_text)
    resp = MODEL.generate_content(prompt)
    raw = (resp.text or "").strip()

    # First try direct JSON parse
    try:
        return json.loads(raw)
    except Exception:
        pass

    # Fallback: extract first {...} block
    try:
        i, j = raw.find("{"), raw.rfind("}")
        if i != -1 and j != -1 and j > i:
            return json.loads(raw[i:j+1])
    except Exception:
        pass

    return {"JD Match": "0", "MissingKeywords": [], "Profile Summary": "(unparseable)"}

def normalize_pct(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s.endswith('%'):
        s = s[:-1]
    try:
        return float(s)
    except Exception:
        return 0.0
