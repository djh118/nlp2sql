import json
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.context import request_id_ctx_var
from app.core.fault_tolerance.error_types import classify_error, build_langfuse_tags
from app.core.fault_tolerance.langfuse_reporter import report_fault_event
from app.core.logging import logger


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_ctx_var.set(request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            category, level, tag = classify_error(e)
            tags = build_langfuse_tags(category, level)
            logger.error(
                f"[{category.value}][{level.value}] {tag}: {e}",
                extra=tags,
            )
            report_fault_event(
                category=category.value,
                level=level.value,
                tag=tag,
                message=f"全局异常: {e}",
                request_id=request_id_ctx_var.get(""),
                metadata={"error_type": type(e).__name__},
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": str(e),
                    "error_category": category.value,
                    "error_tag": tag,
                    "request_id": request_id_ctx_var.get("unknown"),
                },
            )
