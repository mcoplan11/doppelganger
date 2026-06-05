from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker
from datetime import datetime, timezone

from app_config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Saved Qualtrics credentials — auto-populated from the most recent run
    qualtrics_token_enc = Column(Text)
    qualtrics_datacenter = Column(String)

    credits = relationship("CreditBalance", back_populates="user", uselist=False)
    purchases = relationship("Purchase", back_populates="user")
    runs = relationship("Run", back_populates="user")


class CreditBalance(Base):
    __tablename__ = "credits"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    balance = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="credits")


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stripe_session_id = Column(String, unique=True, index=True)
    credits = Column(Integer, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String, default="pending")  # pending | paid | failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="purchases")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Survey info
    original_survey_id = Column(String, nullable=False)
    ai_survey_id = Column(String)         # set after conversion
    qualtrics_datacenter = Column(String, nullable=False)
    # Qualtrics token encrypted at rest (see crypto.py)
    qualtrics_token_enc = Column(Text, nullable=False)

    n_participants = Column(Integer, nullable=False)
    is_smoke_test = Column(Boolean, default=False)
    platform = Column(String, default="prolific")  # prolific | mturk

    # run lifecycle: converting | smoke_test | awaiting_approval | running | done | failed
    status = Column(String, default="converting")
    credits_used = Column(Integer, default=0)
    error = Column(Text)

    # result stored as JSON path (file on disk) or inline for small runs
    result_path = Column(Text)
    branch_summary = Column(Text)  # JSON string of condition counts
    results_json = Column(Text)    # serialized build_results() output; survives Railway deploys

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
    # Updated on every _set_status call so the reaper can tell a legitimately
    # slow run (heartbeat advances) from a Railway-restart orphan (frozen).
    last_heartbeat_at = Column(DateTime)

    user = relationship("User", back_populates="runs")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    import sqlalchemy

    Base.metadata.create_all(bind=engine)
    # Add columns introduced after initial deploy (create_all won't alter existing
    # tables). Each statement runs on its OWN connection: on Postgres a failed
    # statement (e.g. the column already exists) aborts its whole transaction, so
    # sharing one connection lets the first failure swallow every later migration.
    migrations = [
        "ALTER TABLE runs ADD COLUMN platform VARCHAR DEFAULT 'prolific'",
        "ALTER TABLE users ADD COLUMN qualtrics_token_enc TEXT",
        "ALTER TABLE users ADD COLUMN qualtrics_datacenter VARCHAR",
        "ALTER TABLE runs ADD COLUMN last_heartbeat_at TIMESTAMP",
        "ALTER TABLE runs ADD COLUMN results_json TEXT",
    ]
    for sql in migrations:
        try:
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text(sql))
                conn.commit()
        except Exception:
            pass  # column already exists
