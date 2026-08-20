# CLAUDE.md — reranker-service (Akadion)

## Context

Serviciu FastAPI de reranking cross-encoder pentru chatbot-ul RAG Akadion.
Primește chunk-uri de la `llm-response`, le reordonează după relevanță, le întoarce.

Face parte dintr-un sistem de 5 servicii în repo-uri separate. **Acest repo conține
doar reranker-ul.** Nu presupune acces la celelalte servicii și nu propune modificări
în ele.

Serviciul e instrumentat cu OpenTelemetry și exportă span-uri către Jaeger. Logging-ul
e JSON structurat, corelat cu trace-urile. Această corelare e funcțională și verificată —
vezi „Invarianți" mai jos.

---

## Stack

Fix. Nu introduce alternative fără cerere explicită.

| Rol | Alegere |
|---|---|
| Runtime | Python 3.13 |
| Manager pachete | `uv` (pinnat 0.11.26 în Docker) |
| Framework web | FastAPI |
| Validare / modele | Pydantic v2 |
| Model ML | `sentence-transformers` (cross-encoder) |
| Tensor backend | `torch`, de pe indexul **CPU** (`pytorch-cpu`) |
| Tracing | `opentelemetry-distro`, `-exporter-otlp`, `-instrumentation-fastapi` |
| Linting | `ruff` |
| Type checking | `mypy` strict, cu plugin pydantic |
| Teste | `pytest` + `coverage` |

**Nu adăuga dependențe noi.** Dacă o sarcină pare să ceară una, spune asta și oprește-te.

`torch` vine explicit de pe indexul CPU. Nu modifica `[tool.uv.sources]` — fără el se
descarcă ~4.5 GB de wheel-uri NVIDIA.

---

## Structura

Obligatorie. Fișierele noi merg în locul lor din arbore.

```
reranker-service/
├── app/
│   ├── __init__.py
│   ├── main.py                  # punct de intrare: FastAPI(), middleware, rute
│   ├── core/
│   │   ├── __init__.py
│   │   └── models/
│   │       ├── __init__.py      # reexportă din rerank.py
│   │       └── rerank.py        # Chunk, RerankRequest, RerankedChunk, RerankResponse
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── logging_ctx.py       # contextvars (request_id_var)
│   │   ├── logging_setup.py     # JsonFormatter, ContextFilter, setup_logging
│   │   └── middleware.py        # request_context: request_id + log per cerere
│   └── auth/
│       ├── __init__.py
│       └── basic_auth.py
├── docker/
│   ├── Dockerfile
│   └── Dockerfile.multistage    # cel folosit în compose; are opentelemetry-instrument
├── tests/
│   ├── __init__.py              # necesar: fără el mypy se plânge de tests/
│   ├── conftest.py              # FakeCrossEncoder + fixture-uri (client, credențiale)
│   ├── test_main.py             # rerank: ordonare, top_k, scoruri lipsă
│   ├── test_auth.py             # basic auth pe /api/rerank/chunks
│   ├── test_middleware.py       # request_id: generat, preluat, resetat
│   ├── test_logging_json.py     # JsonFormatter: trace_id / span_id
│   └── test_logging_setup.py    # rezolvarea nivelului de log
├── compose.yaml                 # dev local; referă docker/Dockerfile.multistage
├── pyproject.toml               # rămâne în rădăcină (cerință uv/ruff/mypy/pytest)
├── uv.lock                      # idem
├── .dockerignore                # rădăcină: se citește relativ la contextul de build
├── .python-version
├── .gitignore
└── README.md
```

Reguli de plasare:

- `app/main.py` e punct de intrare, nu logică de domeniu. Comanda de pornire e
  `uvicorn app.main:app`. Dacă o schimbi, actualizezi și `docker/Dockerfile*`.
- `core/` = ce *face* serviciul (modele, logica de reranking când se extrage din `main.py`).
- `logging/` = tot ce ține de observabilitate, inclusiv middleware-ul care setează
  `request_id`. Middleware-ul **nu** e cod de auth.
- `core/models/` rămâne un singur fișier (`rerank.py`) cât timp descrie un singur flux.
  Adaugi fișier nou doar pentru alt domeniu, nu pentru altă clasă din același flux.
- Importurile din afara pachetului `models` folosesc reexportul:
  `from app.core.models import RerankRequest`.

Nu crea `utils/`, `helpers/`, `common/`. Codul merge la cel mai îngust scop care îl
justifică.

---

## Invarianți — nu strica astea

Corelarea log ↔ trace funcționează acum. E ușor de rupt tăcut.

1. **`logging_setup.py` citește span-ul curent și scrie `trace_id` / `span_id`**
   formatate pe 32, respectiv 16 hex (format W3C). Aceleași chei sunt folosite de
   backendul Java și de celelalte servicii Python. Nu redenumi cheile, nu schimba
   formatarea.

2. **`request_id`** — cheie cu underscore, 16 hex, header `X-Request-ID`. Identică
   în toate serviciile. Nu o redenumi în `requestId`.

3. **`ctx.is_valid`** — dacă nu există TracerProvider, câmpurile se sar tăcut. De aceea
   `docker/Dockerfile.multistage` pornește sub `opentelemetry-instrument`, și de aceea
   compose-ul îl referă explicit. Nu schimba `Dockerfile`-ul folosit fără să spui asta.

4. **Variabilele `OTEL_*`** vin din compose (endpoint `http://jaeger:4318`, protocol
   `http/protobuf`). Nu le hardcoda în cod.

5. **`contextvars`** — `request_id_var` se setează în middleware și se resetează la final.
   Fără reset, valoarea se scurge între cereri.

---

## Reguli de cod

Ruff e configurat cu: `E, W, F, I, UP, B, SIM, RUF, ANN, ASYNC, S, T20`.
mypy e `strict = true`, `warn_unreachable = true`, plugin pydantic.

Ce înseamnă practic:

- **Toate funcțiile au adnotări complete** — parametri și retur. Inclusiv `-> None`.
- **Fără `print`** (`T20`). Folosește logger-ul.
- **`zip()` primește `strict=`** explicit (`B905`). Într-un reranker, un `zip` care
  trunchiază tăcut face să dispară chunk-uri din răspuns fără nicio eroare.
- **Fără `any`/`Any`** decât ca portiță temporară explicită.
- **Linii ≤ 100 caractere.**
- **Fără cod mort, importuri nefolosite, variabile nefolosite.**
- Comentariile explică *de ce*, nu *ce*. Comentariile de tip `# ← nou` sunt rămășițe
  de migrare — se șterg când atingi zona.
- Early return în loc de imbricare adâncă.
- Fără abstracții premature. La ~300 de linii, nu e nevoie de factory-uri și interfețe.

Testele sunt scutite de `ANN` prin `per-file-ignores` (ruff) și `[[tool.mypy.overrides]]`.
Dacă mypy se plânge totuși de `tests/`, cauza e că lipsește `tests/__init__.py`.

---

## Validare

Înainte de a considera o sarcină terminată:

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```

Toate trei trebuie să treacă fără erori. Nu declara ceva gata pe baza unei citiri —
rulează comenzile.

Nu porni serverul de dezvoltare și nu rula `docker compose up`. Dacă e nevoie de
serviciu pornit, presupune că e deja.

---

## Limite

- **Un commit = o intenție.** Nu amesteca auto-fix cosmetic cu schimbări de logică.
- **Nu restructura ce nu ți s-a cerut.** Migrarea la structura `app/` se face o dată,
  ca sarcină explicită, nu pe bucăți în alte task-uri.
- **Nu modifica `compose.yaml`, `pyproject.toml` sau Dockerfile-urile** ca efect
  secundar al altei sarcini. Dacă o schimbare le cere, spune și așteaptă.
- **Nu atinge `uv.lock`** manual. Doar prin `uv add` / `uv sync`.
- Dacă o sarcină pare să ceară ieșirea din regulile de mai sus, **oprește-te și întreabă**.
  E preferabil unui rezultat care trebuie desfăcut.

---

## Rapoarte

După fiecare sarcină netrivială, scrie un raport în `/vault`:

- nume `AAAA-LL-ZZ-subiect.md`, frontmatter YAML
- **în română**
- ce s-a modificat și **de ce**
- ce concept nou apare — explicat de la zero (destinatarul e începător)
- ce trebuie verificat manual
- `[[wikilinks]]` către note de glosar, create la nevoie
