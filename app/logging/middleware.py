import json
import logging
import time
import uuid
from typing import Protocol, cast

from fastapi import Request
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import AsyncContentStream, Response

from app.logging.logging_ctx import request_id_var

log = logging.getLogger("access")

HEADER = "X-Request-ID"
USER_HEADER = "X-User"
SENSITIVE = {"password", "parola", "token", "secret", "access_token", "authorization"}
MAX_LEN = 2000
OMIS = "<omis>"
SKIP_RESPONSE_PATHS = ("/api/rerank/chunks",)
SKIP_PAYLOAD_PATHS = ("/api/rerank/chunks",)


def _safe(raw: bytes) -> str | None:
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


class _StreamingBody(Protocol):
    """Ce intoarce de fapt call_next: un _StreamingResponse privat al starlette.

    Tipul declarat de RequestResponseEndpoint e Response, care nu are
    body_iterator. Protocolul acopera exact diferenta, fara sa mint tipul
    cu un cast catre StreamingResponse (_StreamingResponse nu deriva din ea).
    """

    body_iterator: AsyncContentStream


async def request_context(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
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

        streaming = cast(_StreamingBody, response)
        chunks = [c async for c in streaming.body_iterator]
        streaming.body_iterator = iterate_in_threadpool(iter(chunks))
        # Content = str | bytes | memoryview; normalizez la bytes pentru join.
        # Doar cand chiar loghez raspunsul — pe /api/rerank/chunks ar fi degeaba.
        raw_response = (
            b"".join(c.encode() if isinstance(c, str) else bytes(c) for c in chunks)
            if log_resp
            else b""
        )

        log.info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                "user": user,
                "payload": _safe(body) if log_payload else OMIS,
                "response": _safe(raw_response) if log_resp else OMIS,
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
                "payload": _safe(body) if log_payload else OMIS,
            },
        )
        raise
    finally:
        request_id_var.reset(token)
