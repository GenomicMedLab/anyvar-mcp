# syntax=docker/dockerfile:1

FROM python:3.13-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.7.22 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

ARG VERSION=0.0.0+docker
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_ANYVAR_MCP=${VERSION} \
    uv sync --no-dev --no-editable --python /usr/local/bin/python

FROM python:3.13-slim-trixie AS runtime
LABEL org.opencontainers.image.source="https://github.com/GenomicMedLab/anyvar-mcp" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.description="MCP server for AnyVar"

RUN python -m pip uninstall --yes pip && \
    groupadd --gid 10001 anyvar && \
    useradd --uid 10001 --gid anyvar --create-home anyvar

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /home/anyvar
USER 10001:10001

ENTRYPOINT ["anyvar-mcp"]
