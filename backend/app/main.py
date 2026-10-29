import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

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


class SPAStaticFiles(StaticFiles):
    """Serve the built frontend; unknown non-API paths get index.html so client-side routes survive a refresh."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


static_dir = config.ROOT / "frontend" / "dist"
if static_dir.is_dir():
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="frontend")
