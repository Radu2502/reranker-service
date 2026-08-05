import json
import logging
import time
import uuid

from fastapi import Request
from starlette.concurrency import iterate_in_threadpool

from logging_ctx import request_id_var

log = logging.getLogger("access")

HEADER = "X-Request-ID"
USER_HEADER = "X-User"
SENSITIVE = {"password", "parola", "token", "secret", "access_token", "authorization"}
MAX_LEN = 2000
SKIP_RESPONSE_PATHS = ("/api/rerank/chunks",)
SKIP_PAYLOAD_PATHS = ("/api/rerank/chunks",)


def _safe(raw: bytes):
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return raw[:MAX_LEN].decode("utf-8", "replace")
    if isinstance(data, dict):
        data = {k: ("***" if k.lower() in SENSITIVE else v) for k, v in data.items()}
    out = json.dumps(data, ensure_ascii=False)
    return out[:MAX_LEN] + ("…" if len(out) > MAX_LEN else "")


async def request_context(request: Request, call_next):
    rid = request.headers.get(HEADER) or uuid.uuid4().hex[:16]
    token = request_id_var.set(rid)
    user = request.headers.get(USER_HEADER) or "anonymous"
    start = time.perf_counter()

    body = await request.body()
    request._body = body

    log_resp = not any(request.url.path.startswith(p) for p in SKIP_RESPONSE_PATHS)
    log_payload = not any(request.url.path.startswith(p) for p in SKIP_PAYLOAD_PATHS)

    try:
        response = await call_next(request)
        response.headers[HEADER] = rid

        chunks = [c async for c in response.body_iterator]
        response.body_iterator = iterate_in_threadpool(iter(chunks))

        log.info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "user": user,
                "payload": _safe(body) if log_payload else "<omis>",
                "response": _safe(b"".join(chunks)) if log_resp else "<omis>",
            },
        )
        return response
    except Exception:
        log.exception(
            "http_error",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "user": user,
                "payload": _safe(body) if log_payload else "<omis>",
            },
        )
        raise
    finally:
        request_id_var.reset(token)