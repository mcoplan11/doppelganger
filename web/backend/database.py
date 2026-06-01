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

    # run lifecycle: converting | smoke_test | awaiting_approval | running | done | failed
    status = Column(String, default="converting")
    credits_used = Column(Integer, default=0)
    error = Column(Text)

    # result stored as JSON path (file on disk) or inline for small runs
    result_path = Column(Text)
    branch_summary = Column(Text)  # JSON string of condition counts

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="runs")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
