# pages/1_HR_Portal.py
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import os
import datetime as dt
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from lib.db import SessionLocal, Job, Application, Interview
from lib.notify import send_email

st.title("HR Portal")

# ---- Create Job (in a form) ----
with st.form("create_job"):
    title = st.text_input("Job Title", placeholder="e.g., Senior Data Analyst")
    jd = st.text_area("Job Description", height=200)
    submit = st.form_submit_button("Create Job")

if submit:
    if title.strip() and jd.strip():
        with SessionLocal() as db:
            job = Job(title=title.strip(), description=jd.strip())
            db.add(job)
            db.commit()
        st.success(f"Job created: {title}")
    else:
        st.warning("Please provide both title and description.")

# ---- Select a job ----
with SessionLocal() as db:
    jobs = db.execute(select(Job).order_by(Job.created_at.desc())).scalars().all()

if not jobs:
    st.info("No jobs yet. Create one above.")
    st.stop()

job_label_to_id = {f"{j.title} (#${j.id})": j.id for j in jobs}
choice = st.selectbox("Select Job", list(job_label_to_id.keys()))
job_id = job_label_to_id[choice]

min_match = st.slider("Minimum Match %", 0, 100, 70, 5)

# ---- Load applications with candidate eagerly loaded ----
with SessionLocal() as db:
    apps = (
        db.query(Application)
        .options(joinedload(Application.candidate))
        .filter(
            Application.job_id == job_id,
            Application.match_pct >= float(min_match),
        )
        .order_by(Application.match_pct.desc(), Application.created_at.desc())
        .all()
    )

if not apps:
    st.info("No candidates meet the threshold yet.")
    st.stop()

# ================
# Custom "table" with action buttons *in the row*
# ================
st.markdown("### Candidates")

# Header row
hcols = st.columns([2.2, 2.2, 1.0, 1.4, 1.2, 1.6, 1.4])
hcols[0].markdown("**Name**")
hcols[1].markdown("**Email**")
hcols[2].markdown("**Match %**")
hcols[3].markdown("**Submitted**")
hcols[4].markdown("**Resume**")
hcols[5].markdown("**Schedule Interview**")
hcols[6].markdown("**Phone**")

# ensure session key for which app to schedule
if "schedule_for_app" not in st.session_state:
    st.session_state["schedule_for_app"] = None

for a in apps:
    c = a.candidate
    match_pct = round(a.match_pct or 0.0, 2)
    submitted = a.created_at.strftime("%Y-%m-%d %H:%M")
    resume_path = a.resume_path
    eligible = match_pct >= 10.0

    cols = st.columns([2.2, 2.2, 1.0, 1.4, 1.2, 1.6, 1.4])

    # Name, Email, Match, Submitted
    cols[0].write(c.name)
    cols[1].write(c.email)
    cols[2].write(f"{match_pct}%")
    cols[3].write(submitted)

    # View/Download Resume (actual PDF control, not the path text)
    try:
        with open(resume_path, "rb") as f:
            cols[4].download_button(
                "View/Download",
                f,
                file_name=os.path.basename(resume_path),
                key=f"dl_{a.id}",
                help="Open or save the candidate's resume PDF",
            )
    except FileNotFoundError:
        cols[4].error("Missing file")

    # Schedule Interview (in-row button; disabled if < 75%)
    cols[5].button(
        "Schedule",
        key=f"schedule_{a.id}",
        disabled=not eligible,
        help="Enabled for candidates with ≥ 75% match",
        on_click=lambda app_id=a.id: st.session_state.__setitem__("schedule_for_app", app_id),
    )

    # Phone (optional)
    cols[6].write(c.phone or "")

# ================
# Schedule form (appears right below the table when a row button is clicked)
# ================
selected_app_id = st.session_state.get("schedule_for_app")
if selected_app_id:
    st.markdown("---")
    st.markdown("### Schedule Interview")

    with SessionLocal() as db:
        app = (
            db.query(Application)
            .options(joinedload(Application.candidate), joinedload(Application.job))
            .filter(Application.id == selected_app_id)
            .one_or_none()
        )

    if app is None:
        st.error("Application not found.")
    else:
        c = app.candidate
        j = app.job

        with st.form("schedule_form", clear_on_submit=False):
            interviewer_name = st.text_input("Interviewer Name *")
            interviewer_email = st.text_input("Interviewer Email *")
            round_choice = st.selectbox("Round *", ["L1", "L2", "HR"])
            date = st.date_input("Interview Date *", value=dt.date.today())
            time = st.time_input("Interview Time *", value=dt.time(10, 0))
            location = st.text_input("Location / Meet Link (optional)")
            notes = st.text_area("Notes (optional)")
            send_btn = st.form_submit_button("Create & Send Invites")

        if send_btn:
            scheduled_dt = dt.datetime.combine(date, time)

            # Save interview
            with SessionLocal() as db:
                interview = Interview(
                    application_id=selected_app_id,
                    round=round_choice,
                    interviewer_name=interviewer_name.strip(),
                    interviewer_email=interviewer_email.strip(),
                    scheduled_at=scheduled_dt,
                    location=(location or "").strip(),
                    notes=(notes or "").strip(),
                )
                db.add(interview)
                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
                    st.error(f"Could not save interview: {e}")
                    st.stop()

            # Emails
            subj = f"[{j.title}] {round_choice} Interview Scheduled — {c.name}"
            when_str = scheduled_dt.strftime("%Y-%m-%d %H:%M")
            loc_str = location or "TBD"

            interviewer_body = (
                f"Hi {interviewer_name},\n\n"
                f"You have a {round_choice} interview scheduled.\n\n"
                f"Candidate: {c.name}\n"
                f"Email: {c.email}\n"
                f"Job: {j.title}\n"
                f"When: {when_str}\n"
                f"Location/Link: {loc_str}\n\n"
                f"Notes: {notes or '—'}\n\n"
                f"Regards,\nHR Portal"
            )

            candidate_body = (
                f"Hi {c.name},\n\n"
                f"Your {round_choice} interview has been scheduled.\n\n"
                f"Role: {j.title}\n"
                f"Interviewer: {interviewer_name}\n"
                f"When: {when_str}\n"
                f"Location/Link: {loc_str}\n\n"
                f"Notes: {notes or '—'}\n\n"
                f"Good luck!\nHR Team"
            )

            try:
                send_email([interviewer_email.strip()], subj, interviewer_body)
                send_email([c.email], subj, candidate_body)
            except Exception as e:
                st.warning(f"Interview saved, but email failed: {e}")
            else:
                st.success("Interview scheduled & emails sent.")
                # Reset so the form hides
                st.session_state["schedule_for_app"] = None
