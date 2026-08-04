import logging
import os
import sys

from logging_ctx import request_id_var


class ContextFilter(logging.Filter):
    """Adauga request_id pe fiecare LogRecord care trece prin handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: str | None = None) -> None:
    level = level or os.getenv("LOG_LEVEL", "INFO")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    for noisy in ("httpx", "httpcore", "huggingface_hub",
                  "sentence_transformers", "uvicorn.access"):
        logging.getLogger(noisy).setLevel("WARNING")