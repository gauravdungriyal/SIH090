import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings
from app.gemini.client import GeminiError
from app.models import Base, engine, migrate_provider_columns

logging.basicConfig(level=logging.INFO)
settings = get_settings()
rate_windows: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_provider_columns(engine)
    yield


app = FastAPI(title="Voice and Catalogue Microservice", version="0.1.0", lifespan=lifespan)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/tester/assets", StaticFiles(directory=static_dir), name="tester-assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    if request.url.path != "/health" and settings.rate_limit_per_minute > 0:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = rate_windows[key]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= settings.rate_limit_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "request_id": request_id,
                    "code": "rate_limited",
                    "message": "Too many requests",
                },
                headers={"X-Request-ID": request_id},
            )
        window.append(now)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(GeminiError)
async def gemini_error(request: Request, exc: GeminiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"request_id": request.state.request_id, "code": exc.code, "message": exc.message},
    )


app.include_router(router)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/tester")


@app.get("/tester", include_in_schema=False)
def tester():
    return FileResponse(static_dir / "index.html")
