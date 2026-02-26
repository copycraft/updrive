# Filename: app/utils.py
from fastapi import HTTPException, status


def ensure_owner(resource_owner_id: int, user_id: int) -> None:
    if resource_owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")