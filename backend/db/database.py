from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.config import settings

# ── Create engine ────────────────────────────
# Engine = connection to our SQLite database file
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# ── Session ───────────────────────────────────
# Session = like opening the database to read/write
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ── Base ──────────────────────────────────────
# Base = parent class all our models inherit from
Base = declarative_base()

# ── get_db ────────────────────────────────────
def get_db():
    """
    Creates a database session for each request
    Closes it automatically when done!
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()