# lib/db.py
import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    ForeignKey, Text, UniqueConstraint, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# -------------------------------
# Database setup
# -------------------------------
# Example: export DATABASE_URL="sqlite:///smart_ats.db"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///smart_ats.db")

# SQLite needs this connect arg when used in frameworks like Streamlit
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


# -------------------------------
# Models
# -------------------------------
class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    applications = relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)  # treat email as identity
    phone = Column(String(64), nullable=True)
    experience_years = Column(Float, nullable=True)
    skills = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    applications = relationship(
        "Application", back_populates="candidate", cascade="all, delete-orphan"
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_app_job_cand"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)

    # Keep these so HR portal filtering keeps working
    match_pct = Column(Float, nullable=False, default=0.0)            # 0..100
    missing_keywords = Column(Text, nullable=False, default="[]")     # JSON-encoded list
    profile_summary = Column(Text, nullable=False, default="")        # text summary

    resume_path = Column(String(1024), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    job = relationship("Job", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")

    # interviews relation added via Interview below
    interviews = relationship(
        "Interview", back_populates="application", cascade="all, delete-orphan"
    )


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)

    # e.g., "L1", "L2", "HR"
    round = Column(String(16), nullable=False)

    interviewer_name = Column(String(120), nullable=False)
    interviewer_email = Column(String(255), nullable=False)

    # Store naive or UTC; your choice. (If you want UTC, convert on write/read.)
    scheduled_at = Column(DateTime, nullable=False)

    location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    application = relationship("Application", back_populates="interviews")


# -------------------------------
# Create tables (for simple setups without Alembic)
# -------------------------------
def init_db():
    Base.metadata.create_all(bind=engine)
