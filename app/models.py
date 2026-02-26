# Filename: app/models.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
import uuid
from .config import settings


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # quota info (logical quota, in bytes)
    used_bytes: int = Field(default=0, nullable=False)
    quota_bytes: int = Field(default=settings.default_user_quota_gb * 1024 * 1024 * 1024, nullable=False)

    files: List["File"] = Relationship(back_populates="owner")
    folders: List["Folder"] = Relationship(back_populates="owner")


class Folder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    owner_id: int = Field(foreign_key="user.id")
    parent_id: Optional[int] = Field(default=None, foreign_key="folder.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    owner: Optional[User] = Relationship(back_populates="folders")
    files: List["File"] = Relationship(back_populates="folder")
    children: List["Folder"] = Relationship(back_populates="parent", sa_relationship_kwargs={"remote_side": "Folder.id"})
    parent: Optional["Folder"] = Relationship(back_populates="children")


class File(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True, unique=True)
    owner_id: int = Field(foreign_key="user.id")
    folder_id: Optional[int] = Field(default=None, foreign_key="folder.id")
    original_name: str
    storage_name: str  # filename on disk (physical object)
    size: int
    mime_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    download_count: int = 0

    sha256: Optional[str] = Field(default=None, index=True)

    owner: Optional[User] = Relationship(back_populates="files")
    folder: Optional[Folder] = Relationship(back_populates="files")