# Filename: webdrive/router.py
import httpx
from fastapi import (
    APIRouter,
    Request,
    Response,
    Form,
    status,
    Depends,
    UploadFile,
    File,
    Header,
)
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional, Dict, Any
from webdrive.config import API_URL, APP_NAME, APP_VERSION
import json

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# helper: get token from cookie
def _token_from_cookie(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    return token

# --- Pages ---
@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("base.html", {"request": request, "app_name": APP_NAME, "app_version": APP_VERSION})

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, msg: Optional[str] = None):
    return templates.TemplateResponse("login.html", {"request": request, "app_name": APP_NAME, "error": msg})

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, msg: Optional[str] = None):
    return templates.TemplateResponse("register.html", {"request": request, "app_name": APP_NAME, "error": msg})

@router.get("/drive", response_class=HTMLResponse)
def drive_page(request: Request):
    # page itself is protected client-side / JS uses /web/api/drive to confirm auth
    return templates.TemplateResponse("drive.html", {"request": request, "app_name": APP_NAME})

# --- Auth proxy endpoints ---
@router.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...), remember: Optional[bool] = Form(False)):
    """
    Proxy login: call backend /auth/token (OAuth2) or /auth/token to get JWT,
    then set HttpOnly cookie on the frontend domain.
    """
    token_url = f"{API_URL}/auth/token"
    # OAuth2PasswordRequestForm expects form fields 'username' and 'password' and grant_type etc.
    # The backend token endpoint in our design accepts form data. We use httpx to post form.
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(token_url, data={"username": username, "password": password})
        except Exception as e:
            return templates.TemplateResponse("login.html", {"request": None, "error": "Backend unreachable"}, status_code=502)
        if r.status_code != 200:
            return templates.TemplateResponse("login.html", {"request": None, "error": "Invalid credentials"}, status_code=401)
        data = r.json()
        token = data.get("access_token")
        if not token:
            return templates.TemplateResponse("login.html", {"request": None, "error": "Login failed, no token"}, status_code=500)
        # set HttpOnly cookie on frontend domain; webdrive server will use this cookie to forward Authorization to backend
        max_age = 60 * 60 * 24 * 30 if remember else None
        resp = RedirectResponse(url="/drive", status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie("access_token", token, httponly=True, secure=False, samesite="lax", max_age=max_age, path="/")
        return resp

@router.post("/logout")
async def logout():
    resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("access_token", path="/")
    return resp

@router.post("/register")
async def register(username: str = Form(...), email: Optional[str] = Form(None), password: str = Form(...)):
    """
    Proxy register: call backend /auth/register
    """
    url = f"{API_URL}/auth/register"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json={"username": username, "email": email, "password": password})
        except Exception:
            return templates.TemplateResponse("register.html", {"request": None, "error": "Backend unreachable"}, status_code=502)
        if r.status_code not in (200, 201):
            # try to surface backend error
            try:
                err = r.json()
            except Exception:
                err = r.text
            return templates.TemplateResponse("register.html", {"request": None, "error": f"Register failed: {err}"}, status_code=400)
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

# --- Proxy API endpoints (same-origin for browser) ---
# These endpoints forward requests to the backend with Authorization header built from the cookie.

async def _forward_headers_from_request(req: Request) -> Dict[str, str]:
    # do not forward host; backend expects our token via Authorization
    headers = {}
    if "user-agent" in req.headers:
        headers["user-agent"] = req.headers["user-agent"]
    return headers

@router.get("/web/api/drive")
async def web_api_drive(request: Request):
    token = _token_from_cookie(request)
    if not token:
        return {"error": "unauthenticated"}, status.HTTP_401_UNAUTHORIZED
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_URL}/api/drive"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

@router.get("/web/api/files")
async def web_api_files(request: Request, limit: int = 50, offset: int = 0, folder_id: Optional[int] = None):
    token = _token_from_cookie(request)
    if not token:
        return {"error": "unauthenticated"}, status.HTTP_401_UNAUTHORIZED
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": limit, "offset": offset}
    if folder_id is not None:
        params["folder_id"] = folder_id
    url = f"{API_URL}/api/files"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

@router.post("/web/api/upload")
async def web_api_upload(request: Request, upload: UploadFile = File(...), folder_id: Optional[int] = Form(None)):
    """
    Accept a multipart upload from browser, forward to backend /api/upload.
    """
    token = _token_from_cookie(request)
    if not token:
        return {"error": "unauthenticated"}, status.HTTP_401_UNAUTHORIZED
    headers = {"Authorization": f"Bearer {token}"}
    # build multipart for httpx
    files = {"upload": (upload.filename, await upload.read(), upload.content_type or "application/octet-stream")}
    data = {}
    if folder_id is not None:
        data["folder_id"] = str(folder_id)
    url = f"{API_URL}/api/upload"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, files=files, data=data)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

@router.get("/web/api/files/{file_id}/download")
async def web_api_download(file_id: int, request: Request):
    """
    Stream download from backend to the browser.
    """
    token = _token_from_cookie(request)
    if not token:
        return {"error": "unauthenticated"}, status.HTTP_401_UNAUTHORIZED
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_URL}/api/files/{file_id}/download"
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.get(url, headers=headers, stream=True)
        if r.status_code != 200:
            return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))
        # stream to client
        async def stream_generator():
            async for chunk in r.aiter_bytes():
                yield chunk
        dispo = r.headers.get("content-disposition")
        media_type = r.headers.get("content-type") or "application/octet-stream"
        headers_resp = {}
        if dispo:
            headers_resp["Content-Disposition"] = dispo
        return StreamingResponse(stream_generator(), media_type=media_type, headers=headers_resp)

@router.delete("/web/api/files/{file_id}")
async def web_api_delete(file_id: int, request: Request):
    token = _token_from_cookie(request)
    if not token:
        return {"error": "unauthenticated"}, status.HTTP_401_UNAUTHORIZED
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_URL}/api/files/{file_id}"
    async with httpx.AsyncClient() as client:
        r = await client.delete(url, headers=headers)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

@router.get("/web/api/usage")
async def web_api_usage(request: Request):
    token = _token_from_cookie(request)
    if not token:
        return {"error": "unauthenticated"}, status.HTTP_401_UNAUTHORIZED
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_URL}/api/usage"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))