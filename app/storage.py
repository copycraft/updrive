# Filename: app/storage.py
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from uuid import uuid4
from .config import settings
import aiofiles
import hashlib

STORAGE_DIR: Path = settings.storage_path / "files"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def make_storage_name(original_filename: str) -> str:
    uid = uuid4().hex
    sanitized = "".join(c for c in original_filename if c.isalnum() or c in " ._-").strip()
    return f"{uid}_{sanitized}"


async def save_upload_file(upload_file: UploadFile, storage_name: str):
    """
    Save UploadFile to disk while computing SHA256. Returns tuple(size_bytes, sha256_hex, filepath).
    """
    dest_path = STORAGE_DIR / storage_name
    h = hashlib.sha256()
    size = 0
    try:
        async with aiofiles.open(dest_path, "wb") as out_file:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                await out_file.write(chunk)
                h.update(chunk)
                size += len(chunk)
    finally:
        try:
            await upload_file.close()
        except Exception:
            pass
    sha256_hex = h.hexdigest()
    return size, sha256_hex, str(dest_path)


def get_file_path(storage_name: str) -> str:
    p = STORAGE_DIR / storage_name
    return str(p) if p.exists() else ""


def delete_storage_file(storage_name: str) -> None:
    p = STORAGE_DIR / storage_name
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass