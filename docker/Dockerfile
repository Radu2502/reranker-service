FROM python:3.13-slim

# Versiune pinnată: un build peste trei luni trebuie să folosească același uv.
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

# Logurile apar imediat în docker logs, fără buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Stratul de dependențe, separat de cod: o modificare în main.py
# nu invalidează cache-ul pentru cele 71 de pachete.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project && \
    uv cache clean

# Modelul copt în imagine (~470 MB): pornire rapidă, fără rețea la runtime.
ENV HF_HOME=/opt/hf
RUN uv run python -c "\
from sentence_transformers import CrossEncoder; \
CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1')"

COPY . .
RUN uv sync --locked --no-dev

EXPOSE 8002

CMD ["uv", "run", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8002"]