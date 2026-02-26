# Filename: app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..db import engine
from ..models import User
from ..schemas import Token, UserCreate, UserOut
from ..auth import get_password_hash, verify_password, create_access_token, get_user_by_username
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate):
    with Session(engine) as session:
        existing = get_user_by_username(session, user_in.username)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
        hashed = get_password_hash(user_in.password)
        user = User(username=user_in.username, email=user_in.email, hashed_password=hashed)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@router.post("/token", response_model=Token)
def login_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        statement = select(User).where(User.username == form_data.username)
        user = session.exec(statement).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
        token = create_access_token(user.username)
        return {"access_token": token, "token_type": "bearer"}


# JSON login that sets HttpOnly cookie (works for browsers)
@router.post("/login-cookie")
def login_cookie(response: Response, username: str = Body(...), password: str = Body(...), remember: bool = Body(False)):
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
        token = create_access_token(user.username)
        # set cookie: httponly, secure should be True in prod (HTTPS)
        max_age = 60 * 60 * 24 * 30 if remember else None  # 30 days or session cookie
        response.set_cookie("access_token", token, httponly=True, secure=False, samesite="lax", max_age=max_age)
        return {"status": "ok"}


# Logout clears cookie
@router.post("/logout-cookie")
def logout_cookie(response: Response):
    response.delete_cookie("access_token")
    return {"status": "ok"}