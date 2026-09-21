from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class SpandanException(Exception):  # noqa: N818 - public API exception name
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Any] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def create_error_response(code: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def create_success_response(
    message: str, data: Optional[Any] = None
) -> Dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
    }


async def spandan_exception_handler(request: Request, exc: SpandanException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            code=exc.code, message=exc.message, details=exc.details
        ),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=create_error_response(
            code="VALIDATION_ERROR",
            message="Input validation failed.",
            details=details,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        401: "INVALID_CREDENTIALS",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_SERVER_ERROR",
    }
    code = code_map.get(exc.status_code, "ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "HTTP Exception"
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(code=code, message=message),
    )


async def integrity_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content=create_error_response(
        code="CONFLICT", message="This change conflicts with an existing record. Please refresh and try again."
    ))
