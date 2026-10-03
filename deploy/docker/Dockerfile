# One OCI image for every Python deployable (ADR-0016, X01 issue #44).
#
# `clarity-api`, `clarity-mcp`, `clarity-channel-gateway` and `hutch-sim` all
# import the same `clarity` package, so they are one image run with different
# commands, which is what plan 21 section 11.1 scenario S1 describes. Building
# four nearly identical images would mean four things to patch when a CVE
# lands in the base layer.
#
# The contract this image has to meet (ADR-0016): config from the environment,
# stateless, health probes, graceful shutdown, a separate migration command,
# JSON logs, and no secrets baked in.

FROM python:3.12-slim-bookworm AS build

# Build dependencies for psycopg and confluent-kafka wheels that have no
# manylinux build for this platform. Not carried into the runtime stage.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY backend/pyproject.toml backend/README.md ./backend/
COPY backend/src ./backend/src

# Installed into a virtualenv so the runtime stage can copy one directory.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "./backend[postgres,kafka,otlp]"


FROM python:3.12-slim-bookworm AS runtime

# Non-root, and not uid 1000: a named account makes an audit of a running
# container readable, and nothing in the image needs to write to its own files.
RUN useradd --system --create-home --uid 10001 clarity

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
# Policy artefacts and rule packs are read at runtime and are not secrets.
# They are versioned with the code on purpose: a decision has to be replayable
# against the exact pack that made it (I10, I11).
COPY --chown=clarity:clarity rules ./rules
COPY --chown=clarity:clarity config ./config
COPY --chown=clarity:clarity services ./services

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CLARITY_PROFILE=full

USER clarity
EXPOSE 8000

# Overridden per deployable by the Helm chart. The default is the money path.
CMD ["uvicorn", "clarity.entrypoints.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
