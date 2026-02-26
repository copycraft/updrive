# Filename: app/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    created_at: datetime
    used_bytes: int
    quota_bytes: int

    model_config = ConfigDict(from_attributes=True)


class FileOut(BaseModel):
    id: int
    uuid: str
    original_name: str
    size: int
    mime_type: Optional[str]
    created_at: datetime
    download_count: int
    sha256: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class FolderOut(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriveListing(BaseModel):
    folders: List[FolderOut]
    files: List[FileOut]

    model_config = ConfigDict(from_attributes=True)


class UsageOut(BaseModel):
    used_bytes: int
    quota_bytes: int
    available_bytes: int

    model_config = ConfigDict(from_attributes=True)