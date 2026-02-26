# Filename: app/db.py
from sqlmodel import SQLModel, create_engine, Session
from .config import settings

DATABASE_URL = settings.database_url

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create DB tables and storage dirs"""
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    (settings.storage_path / "files").mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session():
    """Yield a DB session (dependency)."""
    with Session(engine) as session:
        yield session