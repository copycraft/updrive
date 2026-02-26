# Filename: webdrive/main.py
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from webdrive.router import router as webdrive_router
from webdrive.config import FRONTEND_PORT, APP_NAME, APP_VERSION

app = FastAPI(title=f"{APP_NAME} Frontend", version=APP_VERSION, debug=True)

# mount static folder (JS/CSS)
app.mount("/static", StaticFiles(directory="webdrive/static"), name="static")

# include router (templates + proxy API endpoints)
app.include_router(webdrive_router)