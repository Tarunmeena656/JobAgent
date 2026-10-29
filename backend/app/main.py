import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .db import Base, engine
from .routers import admin, applications, auth, dashboard, jobs, notifications, profile, resumes, runs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="JobAgent", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for router in (auth, profile, resumes, jobs, applications, dashboard, notifications, runs, admin):
    app.include_router(router.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


static_dir = config.ROOT / "frontend" / "dist"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
