import logging
import os
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.exceptions import (
    SpandanException,
    create_success_response,
    http_exception_handler,
    integrity_exception_handler,
    spandan_exception_handler,
    validation_exception_handler,
)
from app.db.session import engine

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="AI-Assisted Appointment Booking & Private Chamber Management System",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(GZipMiddleware, minimum_size=1000)
if settings.FORCE_HTTPS:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_safety_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    content_length = request.headers.get("content-length")
    try:
        payload_too_large = bool(
            content_length and int(content_length) > settings.MAX_REQUEST_SIZE_BYTES
        )
    except ValueError:
        payload_too_large = False
    if payload_too_large:
        return JSONResponse(
            status_code=413,
            content={
                "success": False,
                "error": {"code": "PAYLOAD_TOO_LARGE", "message": "Request body is too large."},
            },
            headers={"X-Request-ID": request_id},
        )
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api/") else "no-cache"
    )
    logger.info(
        "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (time.monotonic() - started) * 1000,
    )
    return response

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.add_exception_handler(IntegrityError, integrity_exception_handler)
app.add_exception_handler(SpandanException, spandan_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

app.include_router(api_router)


@app.get("/", tags=["Health"])
async def root():
    return create_success_response(
        message=f"{settings.APP_NAME} API is running.",
        data={"version": settings.APP_VERSION, "env": settings.APP_ENV},
    )


@app.get("/health/live", tags=["Health"], include_in_schema=False)
async def liveness_check():
    return create_success_response(message="Healthy", data={"status": "OK"})


@app.get("/health/ready", tags=["Health"], include_in_schema=False)
async def readiness_check():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("database_readiness_check_failed")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "NOT_READY", "message": "Database is unavailable."},
            },
        )
    return create_success_response(message="Ready", data={"status": "OK"})


@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check():
    return await readiness_check()
