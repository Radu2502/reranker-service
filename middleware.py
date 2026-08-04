import logging
import time
import uuid

from fastapi import Request

from logging_ctx import request_id_var

log = logging.getLogger("access")

HEADER = "X-Request-ID"


async def request_context(request: Request, call_next):
    rid = request.headers.get(HEADER) or uuid.uuid4().hex[:16]
    token = request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers[HEADER] = rid
        log.info(
            "%s %s -> %d in %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response
    except Exception:
        log.exception("%s %s -> eroare", request.method, request.url.path)
        raise
    finally:
        request_id_var.reset(token)