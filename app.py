# app.py
import os
import streamlit as st
from dotenv import load_dotenv
from lib.db import init_db


st.set_page_config(page_title="Smart ATS", page_icon="🧠", layout="wide")
load_dotenv()
init_db()


st.title("Smart ATS — Company Portal")


st.markdown(
"""
**Welcome!** Use the pages on the left:


- **HR Portal**: Create jobs, review candidates who meet your match threshold, and download resumes.
- **Candidate Apply**: Candidates submit details and upload a resume for a specific job.

"""
)