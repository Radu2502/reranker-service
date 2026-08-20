import json
import logging
import re

from opentelemetry.sdk.trace import TracerProvider

from app.logging.logging_setup import JsonFormatter

HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")


def _record(msg: str = "test_msg") -> logging.LogRecord:
    return logging.LogRecord("app.test", logging.INFO, "app/test.py", 1, msg, (), None)


def _format(record: logging.LogRecord) -> dict[str, str]:
    payload: dict[str, str] = json.loads(JsonFormatter().format(record))
    return payload


def test_fara_span_valid_cheile_de_trace_lipsesc():
    # Fara TracerProvider, ctx.is_valid e False si campurile se sar tacut —
    # logul trebuie sa ramana JSON valid, nu sa crape sau sa scrie zerouri.
    payload = _format(_record())

    assert "trace_id" not in payload
    assert "span_id" not in payload
    assert payload["msg"] == "test_msg"
    assert payload["request_id"] == "-"  # cheie cu underscore, nu requestId


def test_cu_span_valid_apar_trace_id_si_span_id():
    tracer = TracerProvider().get_tracer(__name__)

    with tracer.start_as_current_span("span-de-test") as span:
        payload = _format(_record())
        ctx = span.get_span_context()

    assert payload["trace_id"] == format(ctx.trace_id, "032x")
    assert payload["span_id"] == format(ctx.span_id, "016x")


def test_formatul_hex_e_cel_din_w3c():
    # 32 respectiv 16 hex minuscule. Backendul Java si celelalte servicii
    # Python coreleaza dupa fix formatul asta.
    tracer = TracerProvider().get_tracer(__name__)

    with tracer.start_as_current_span("span-de-test"):
        payload = _format(_record())

    assert HEX32.match(payload["trace_id"]), payload["trace_id"]
    assert HEX16.match(payload["span_id"]), payload["span_id"]


def test_span_ul_curent_dicteaza_id_urile():
    tracer = TracerProvider().get_tracer(__name__)

    with tracer.start_as_current_span("parinte") as parinte:
        de_afara = _format(_record())
        with tracer.start_as_current_span("copil") as copil:
            de_dinauntru = _format(_record())

    # acelasi trace, span-uri diferite: logul urmeaza span-ul activ, nu trace-ul
    assert de_afara["trace_id"] == de_dinauntru["trace_id"]
    assert de_afara["span_id"] == format(parinte.get_span_context().span_id, "016x")
    assert de_dinauntru["span_id"] == format(copil.get_span_context().span_id, "016x")
    assert de_afara["span_id"] != de_dinauntru["span_id"]
