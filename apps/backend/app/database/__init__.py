"""Database engine, session management and migration integration for HaritAyush backend."""

from __future__ import annotations

import os
import sqlite3

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.orm import sessionmaker

# Import Base from the models package using absolute import
from app.models import Base  # shared declarative base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///haritayush.db")
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    """Return a new session."""
    return session_factory()


def init_db() -> None:
    """Initialize the database: create all tables and required indexes.

    Must be called once after engine creation. Safely ensures all tables
    and required indexes exist.
    """
    # Create all tables via SQLAlchemy
    Base.metadata.create_all(engine)

    # Create required indexes safely across engine connections
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_readings_ts ON readings (ts)",
        "CREATE INDEX IF NOT EXISTS ix_forecasts_site_ts ON forecasts (site_id, ts)",
        "CREATE INDEX IF NOT EXISTS ix_recommendations_site_id ON recommendations (site_id)",
        "CREATE INDEX IF NOT EXISTS ix_decisions_site_id ON decisions (site_id)",
        "CREATE INDEX IF NOT EXISTS ix_commands_site_id_status ON commands (site_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_records (ts)",
    ]

    from sqlalchemy import text
    with engine.begin() as conn:
        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
            except Exception:
                pass
