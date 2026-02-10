FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock /tmp/uv-tmp/

RUN cd /tmp/uv-tmp && uv sync --no-cache \
    && rm -rf /tmp/uv-tmp
