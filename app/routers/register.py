# Filename: app/routers/register.py
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, constr
from sqlmodel import Session, select
from app.db import get_session, engine
from app.models import User
from app.auth import get_password_hash

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: constr(min_length=3, max_length=32)
    email: EmailStr
    password: constr(min_length=6)

class RegisterResponse(BaseModel):
    id: int
    username: str
    email: str

@router.post("/register", response_model=RegisterResponse)
def register_user(data: RegisterRequest, session: Session = Depends(get_session)):
    # Check if username or email already exists
    statement = select(User).where((User.username == data.username) | (User.email == data.email))
    existing_user = session.exec(statement).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    # Create user
    hashed_password = get_password_hash(data.password)
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hashed_password
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return RegisterResponse(id=user.id, username=user.username, email=user.email)