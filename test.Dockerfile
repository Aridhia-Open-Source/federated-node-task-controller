FROM python:3.13.5-slim

COPY controller /app/controller
COPY --chmod=755 scripts/tests/*.sh /app/scripts/
COPY pyproject.toml /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        gcc jq curl openssl tar \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv sync --extra dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app/controller
ENV PATH="/app/.venv/bin:$PATH"
CMD ["/app/scripts/test-entrypoint.sh"]
