import re
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.logging.logging_ctx import request_id_var
from app.logging.middleware import HEADER, request_context

HEX16 = re.compile(r"^[0-9a-f]{16}$")
CALE = "/vazut"
RID_TRIMIS = "abc123abc123abc1"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client():
    # App separat, cu o ruta care raporteaza ce vede contextvar-ul *in timpul*
    # cererii. app.main nu expune asa ceva, si nu-l modificam ca sa testam.
    app = FastAPI()
    app.middleware("http")(request_context)

    @app.get(CALE)
    def vazut():
        return {"rid": request_id_var.get()}

    return TestClient(app)


def _cerere(
    headers: dict[str, str] | None = None, path: str = CALE, body: bytes = b""
) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": raw,
        "scheme": "http",
        "root_path": "",
        "client": ("test", 1),
        "server": ("test", 80),
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def _raspuns(payload: bytes = b'{"ok": true}') -> StreamingResponse:
    async def flux() -> AsyncIterator[bytes]:
        yield payload

    return StreamingResponse(flux(), status_code=200)


def test_request_id_generat_cand_lipseste_headerul(client):
    r = client.get(CALE)
    rid = r.json()["rid"]

    assert HEX16.match(rid), f"asteptam 16 hex, am primit {rid!r}"
    assert r.headers[HEADER] == rid  # acelasi id se intoarce si in raspuns


def test_request_id_preluat_din_header_cand_exista(client):
    trimis = "deadbeefdeadbeef"
    r = client.get(CALE, headers={HEADER: trimis})

    assert r.json()["rid"] == trimis  # nu se genereaza altul peste
    assert r.headers[HEADER] == trimis


def test_request_id_nu_se_scurge_de_la_o_cerere_la_alta(client):
    primul = client.get(CALE, headers={HEADER: "1111111111111111"}).json()["rid"]
    al_doilea = client.get(CALE).json()["rid"]

    assert primul == "1111111111111111"
    assert al_doilea != primul
    assert HEX16.match(al_doilea)


@pytest.mark.anyio
async def test_contextvar_resetat_dupa_cerere():
    # Apelam middleware-ul direct, in contextul testului: doar asa se vede
    # efectul lui reset(). Prin TestClient, cererea ruleaza in alt context si
    # o scurgere ar fi invizibila de aici.
    assert request_id_var.get() == "-"
    vazut = {}

    async def call_next(request):
        vazut["rid"] = request_id_var.get()
        return _raspuns()

    r = await request_context(_cerere({HEADER: RID_TRIMIS}), call_next)

    assert vazut["rid"] == RID_TRIMIS  # setat pe durata cererii
    assert r.headers[HEADER] == RID_TRIMIS
    assert request_id_var.get() == "-"  # si pus la loc dupa


@pytest.mark.anyio
async def test_contextvar_resetat_si_cand_cererea_crapa():
    assert request_id_var.get() == "-"

    async def call_next(request):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await request_context(_cerere(), call_next)

    assert request_id_var.get() == "-"  # finally, nu doar calea fericita
