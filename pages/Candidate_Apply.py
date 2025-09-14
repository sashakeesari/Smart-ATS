# pages/2_Candidate_Apply.py
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import json
import re
import streamlit as st
from sqlalchemy import select

from lib.db import SessionLocal, Job, Candidate, Application
from lib.pdf_utils import extract_pdf_text_from_upload  # must return text for text-based PDFs

# -------------------------------
# Setup
# -------------------------------
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

st.title("Apply to a Job")

# -------------------------------
# Load Jobs
# -------------------------------
with SessionLocal() as db:
    jobs = db.execute(select(Job).order_by(Job.created_at.desc())).scalars().all()

if not jobs:
    st.info("No open jobs at the moment.")
    st.stop()

job_map = {f"{j.title} (#{j.id})": j.id for j in jobs}

label = st.selectbox("Select Job", list(job_map.keys()))
job_id = job_map[label]
current_job = next(j for j in jobs if j.id == job_id)

with st.expander("View Job Description"):
    st.write(current_job.description)

# -------------------------------
# Simple keyword-based scorer (resume+skills vs JD)
# -------------------------------
STOPWORDS = {
    "and","or","the","a","an","to","for","in","of","on","at","by","with","is","are",
    "was","were","be","been","it","as","that","this","these","those","from","into",
    "your","you","we","our","their","they","i","he","she","them","us","will","can",
    "may","might","should","could","would","over","under","between","within","per",
    "using","use","used","etc","&","+","-","/","\\"
}

TECH_KEEP = {"c", "c++", "c#", "go", "r", "sql"}  # don't drop short tech tokens

def tokenize(text: str) -> list[str]:
    # capture words, digits, and common tech tokens (#, +, .)
    words = re.findall(r"[A-Za-z0-9+#\.]{1,}", (text or "").lower())
    out = []
    for w in words:
        if w in STOPWORDS:
            continue
        # keep very short only if technical (e.g., 'c', 'r')
        if len(w) < 2 and w not in TECH_KEEP:
            continue
        # drop single-character punctuation-like tokens
        if len(w) == 1 and w not in TECH_KEEP:
            continue
        out.append(w)
    return out

def keywords_from_text(text: str, top_cap: int = 120) -> set[str]:
    toks = tokenize(text)
    freq = {}
    for t in toks:
        freq[t] = freq.get(t, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    keep = [w for w, c in ranked if c >= 2]
    if len(keep) < 40:
        keep = [w for w, _ in ranked][:top_cap]
    return set(keep[:top_cap])

def compute_match(resume_text: str, jd_text: str, extra_skills_csv: str = ""):
    jd_keys = keywords_from_text(jd_text)
    res_words = set(tokenize(resume_text))

    # include typed skills as additional evidence
    if extra_skills_csv.strip():
        for s in re.split(r"[,\n;]+", extra_skills_csv.lower()):
            s = s.strip()
            if s:
                res_words.update(tokenize(s))

    if not jd_keys:
        return 0.0, [], ""

    overlap = jd_keys & res_words
    match_pct = (len(overlap) / len(jd_keys)) * 100.0
    missing = sorted(list(jd_keys - res_words))[:20]
    summary = ""  # keep empty per your requirement

    return max(0.0, min(100.0, match_pct)), missing, summary

# -------------------------------
# Candidate Form
# -------------------------------
st.subheader("Your Details")
with st.form("apply", clear_on_submit=False):
    name = st.text_input("Full Name *")
    email = st.text_input("Email *")
    phone = st.text_input("Phone")
    exp_years = st.number_input(
        "Years of Experience", min_value=0.0, max_value=60.0, value=0.0, step=0.5
    )
    skills = st.text_area("Key Skills (comma-separated)")
    resume_up = st.file_uploader("Upload Resume (PDF) *", type=["pdf"])
    submit = st.form_submit_button("Submit Application")

if not submit:
    st.stop()

if not (name.strip() and email.strip() and resume_up is not None):
    st.warning("Please fill required fields and upload your resume.")
    st.stop()

# -------------------------------
# Save resume
# -------------------------------
safe_email = email.strip().lower()
base_name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name.strip()) or "resume"
fname = f"{base_name}_{uuid.uuid4().hex[:8]}.pdf"
fpath = UPLOAD_DIR / fname
with open(fpath, "wb") as out:
    out.write(resume_up.getbuffer())

# -------------------------------
# Extract + score
# -------------------------------
try:
    resume_text = extract_pdf_text_from_upload(resume_up) or ""
except Exception:
    resume_text = ""

match_pct, missing, summary = compute_match(resume_text, current_job.description, skills)

# -------------------------------
# Upsert Candidate + Application
# -------------------------------
with SessionLocal() as db:
    cand = db.query(Candidate).filter(Candidate.email == safe_email).one_or_none()
    if cand is None:
        cand = Candidate(
            name=name.strip(),
            email=safe_email,
            phone=(phone or "").strip(),
            experience_years=float(exp_years),
            skills=(skills or "").strip(),
        )
        db.add(cand)
        db.flush()
    else:
        cand.name = name.strip()
        cand.phone = (phone or "").strip()
        cand.experience_years = float(exp_years)
        cand.skills = (skills or "").strip()

    app = (
        db.query(Application)
        .filter(Application.job_id == job_id, Application.candidate_id == cand.id)
        .one_or_none()
    )

    if app:
        app.resume_path = str(fpath)
        app.match_pct = float(match_pct)
        app.missing_keywords = json.dumps(missing, ensure_ascii=False)
        app.profile_summary = summary
        message = f"✅ Application updated for: {current_job.title} — JD Match: {match_pct:.1f}%"
    else:
        app = Application(
            job_id=job_id,
            candidate_id=cand.id,
            match_pct=float(match_pct),
            missing_keywords=json.dumps(missing, ensure_ascii=False),
            profile_summary=summary,
            resume_path=str(fpath),
        )
        db.add(app)
        message = f"✅ Application submitted for: {current_job.title} — JD Match: {match_pct:.1f}%"

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        st.error(f"Could not save application: {e}")
        st.stop()

# -------------------------------
# Confirmation UI
# -------------------------------
st.success(message)
if missing:
    st.info("Consider adding keywords: " + ", ".join(missing))
