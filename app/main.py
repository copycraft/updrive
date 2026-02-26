# app/router.py
from fastapi import FastAPI
# ... imports ...
# Routers
from .routers import auth as auth_router, files as files_router, root as root_router, router as register_router
from .config import settings
from .db import init_db
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)

origins = ["*"] if settings.cors_allow_origins == "*" else [o.strip() for o in settings.cors_allow_origins.split(",")]
allow_methods = ["*"] if settings.cors_allow_methods == "*" else [m.strip() for m in settings.cors_allow_methods.split(",")]
allow_headers = ["*"] if settings.cors_allow_headers == "*" else [h.strip() for h in settings.cors_allow_headers.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
)

app.include_router(auth_router.router)
app.include_router(files_router.router)
app.include_router(root_router.router)

app.include_router(register_router)

@app.on_event("startup")
def on_startup():
    init_db()