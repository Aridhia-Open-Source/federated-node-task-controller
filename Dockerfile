FROM python:3.13.5-slim

COPY controller /app/controller
COPY pyproject.toml /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        gcc gh jq curl openssl tar \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv sync \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# hadolint ignore=DL3013,DL3008
RUN curl -sSL -O https://packages.microsoft.com/config/debian/"$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2)"/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install --no-install-recommends -y azcopy \
    && echo "Checking installed azcopy version:" \
    && azcopy --version \
    && rm packages-microsoft-prod.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app/controller
ENV PATH="/.venv/bin:$PATH"
CMD ["python3", "-m", "controller"]
