# Filename: app/routers/files.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks, Query, Body
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from ..db import engine
from ..models import File as FileModel, Folder, User
from ..schemas import FileOut, FolderCreate, FolderOut, DriveListing, UsageOut
from ..auth import get_current_user
from ..storage import make_storage_name, save_upload_file, get_file_path, delete_storage_file
from ..utils import ensure_owner
from ..config import settings
import mimetypes
import os

router = APIRouter(prefix="/api", tags=["files"])


# --- Upload file with quota + dedupe ---
@router.post("/upload", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    upload: UploadFile = File(...),
    folder_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    # enforce max upload size (quick guard, may not be perfect for all upload backends)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    # We cannot always know the upload size in advance; we will check after writing and before DB commit.

    storage_name = make_storage_name(upload.filename)
    size, sha256_hex, saved_path = await save_upload_file(upload, storage_name)

    if size > max_bytes:
        # remove saved file and reject
        try:
            os.remove(saved_path)
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Uploaded file exceeds max_upload_size_mb")

    # Start DB transaction
    with Session(engine) as session:
        # folder checks
        if folder_id:
            folder = session.get(Folder, folder_id)
            if not folder:
                # cleanup saved file
                try:
                    os.remove(saved_path)
                except Exception:
                    pass
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
            if folder.owner_id != current_user.id:
                try:
                    os.remove(saved_path)
                except Exception:
                    pass
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to folder")

        # check quota (logical usage: each user counts the file size against quota)
        # refresh user
        user = session.get(User, current_user.id)
        if user is None:
            try:
                os.remove(saved_path)
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if user.used_bytes + size > user.quota_bytes:
            # over quota -> cleanup saved file and error
            try:
                os.remove(saved_path)
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Upload would exceed your quota")

        # dedup: see if a physical object with same sha256 already exists
        existing_stmt = select(FileModel).where(FileModel.sha256 == sha256_hex)
        existing = session.exec(existing_stmt).first()

        if existing:
            # been uploaded before; delete the newly saved duplicate (we'll reuse existing.storage_name)
            try:
                os.remove(saved_path)
            except Exception:
                pass
            storage_used_name = existing.storage_name
            physical_size = existing.size
        else:
            # new physical object, we already stored it as `storage_name`
            storage_used_name = storage_name
            physical_size = size

        # create user file metadata record (logical file)
        f = FileModel(
            owner_id=user.id,
            folder_id=folder_id,
            original_name=upload.filename,
            storage_name=storage_used_name,
            size=size,
            mime_type=upload.content_type or mimetypes.guess_type(upload.filename)[0] or "application/octet-stream",
            sha256=sha256_hex,
        )
        session.add(f)

        # update user's used_bytes (logical usage)
        user.used_bytes = user.used_bytes + size
        session.add(user)

        session.commit()
        session.refresh(f)
        session.refresh(user)

        # return Pydantic model from ORM
        return FileOut.from_orm(f)


@router.get("/files", response_model=List[FileOut])
def list_files(limit: int = 50, offset: int = 0, folder_id: Optional[int] = None, current_user=Depends(get_current_user)):
    with Session(engine) as session:
        stmt = select(FileModel).where(FileModel.owner_id == current_user.id)
        if folder_id is not None:
            stmt = stmt.where(FileModel.folder_id == folder_id)
        stmt = stmt.order_by(FileModel.created_at.desc()).limit(limit).offset(offset)
        results = session.exec(stmt).all()
        return [FileOut.from_orm(f) for f in results]


@router.get("/drive", response_model=DriveListing)
def drive_list(folder_id: Optional[int] = None, current_user=Depends(get_current_user)):
    with Session(engine) as session:
        # folders
        fstmt = select(Folder).where(Folder.owner_id == current_user.id)
        if folder_id is None:
            fstmt = fstmt.where(Folder.parent_id == None)  # root folders
        else:
            fstmt = fstmt.where(Folder.parent_id == folder_id)
        fstmt = fstmt.order_by(Folder.created_at.desc())
        folders = session.exec(fstmt).all()

        # files
        stmt = select(FileModel).where(FileModel.owner_id == current_user.id)
        if folder_id is None:
            stmt = stmt.where(FileModel.folder_id == None)
        else:
            stmt = stmt.where(FileModel.folder_id == folder_id)
        stmt = stmt.order_by(FileModel.created_at.desc())
        files = session.exec(stmt).all()

        return DriveListing(
            folders=[FolderOut.from_orm(d) for d in folders],
            files=[FileOut.from_orm(f) for f in files],
        )


@router.get("/files/{file_id}/download")
def download_file(file_id: int, background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
    with Session(engine) as session:
        f = session.get(FileModel, file_id)
        if not f:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        ensure_owner(f.owner_id, current_user.id)
        path = get_file_path(f.storage_name)
        if not path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk")

        def inc_count(file_pk: int):
            with Session(engine) as s:
                obj = s.get(FileModel, file_pk)
                if obj:
                    obj.download_count += 1
                    s.add(obj)
                    s.commit()

        background_tasks.add_task(inc_count, f.id)
        return FileResponse(path, media_type=f.mime_type or "application/octet-stream", filename=f.original_name)


@router.post("/files/{file_id}/rename", response_model=FileOut)
def rename_file(file_id: int, new_name: str = Body(..., embed=True), current_user=Depends(get_current_user)):
    with Session(engine) as session:
        f = session.get(FileModel, file_id)
        if not f:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        ensure_owner(f.owner_id, current_user.id)
        f.original_name = new_name
        session.add(f)
        session.commit()
        session.refresh(f)
        return FileOut.from_orm(f)


@router.post("/files/{file_id}/move", response_model=FileOut)
def move_file(file_id: int, folder_id: Optional[int] = Body(None, embed=True), current_user=Depends(get_current_user)):
    with Session(engine) as session:
        f = session.get(FileModel, file_id)
        if not f:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        ensure_owner(f.owner_id, current_user.id)
        if folder_id is not None:
            folder = session.get(Folder, folder_id)
            if not folder:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination folder not found")
            if folder.owner_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to destination folder")
        f.folder_id = folder_id
        session.add(f)
        session.commit()
        session.refresh(f)
        return FileOut.from_orm(f)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: int, current_user=Depends(get_current_user)):
    with Session(engine) as session:
        f = session.get(FileModel, file_id)
        if not f:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        ensure_owner(f.owner_id, current_user.id)

        user = session.get(User, current_user.id)
        if user:
            # subtract logical usage (don't go negative)
            user.used_bytes = max(0, user.used_bytes - f.size)
            session.add(user)

        others_stmt = select(FileModel).where(FileModel.storage_name == f.storage_name, FileModel.id != f.id)
        others = session.exec(others_stmt).first()
        if not others:
            # no other references -> delete physical file
            try:
                delete_storage_file(f.storage_name)
            except Exception:
                pass

        session.delete(f)
        session.commit()
        return


@router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(data: FolderCreate, current_user=Depends(get_current_user)):
    with Session(engine) as session:
        if data.parent_id:
            parent = session.get(Folder, data.parent_id)
            if not parent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
            if parent.owner_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to parent folder")
        folder = Folder(owner_id=current_user.id, name=data.name, parent_id=data.parent_id)
        session.add(folder)
        session.commit()
        session.refresh(folder)
        return FolderOut.from_orm(folder)


@router.get("/folders", response_model=List[FolderOut])
def list_folders(current_user=Depends(get_current_user)):
    with Session(engine) as session:
        stmt = select(Folder).where(Folder.owner_id == current_user.id).order_by(Folder.created_at.desc())
        results = session.exec(stmt).all()
        return [FolderOut.from_orm(f) for f in results]


@router.get("/usage", response_model=UsageOut)
def get_usage(current_user=Depends(get_current_user)):
    with Session(engine) as session:
        user = session.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        available = max(0, user.quota_bytes - user.used_bytes)
        return UsageOut(used_bytes=user.used_bytes, quota_bytes=user.quota_bytes, available_bytes=available)