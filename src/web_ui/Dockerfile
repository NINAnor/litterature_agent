FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

ADD . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

ENTRYPOINT ["/app/src/web_ui/entrypoint.sh"]
CMD ["uv", "run", "paper-agent-ui"]
