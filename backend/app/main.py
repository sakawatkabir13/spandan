import os
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import settings
from app.core.exceptions import (
    SpandanException,
    create_success_response,
    http_exception_handler,
    spandan_exception_handler,
    validation_exception_handler,
)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="AI-Assisted Appointment Booking & Private Chamber Management System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.add_exception_handler(SpandanException, spandan_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

app.include_router(api_router)


@app.get("/", tags=["Health"])
async def root():
    return create_success_response(
        message=f"{settings.APP_NAME} API is running.",
        data={"version": "0.1.0", "env": settings.APP_ENV},
    )


@app.get("/health", tags=["Health"])
async def health_check():
    return create_success_response(message="Healthy", data={"status": "OK"})
