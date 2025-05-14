FROM python:3.12.2-slim

COPY controller /app/controller
COPY Pipfile* /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# hadolint detects pipenv as another invocation of pip
# hadolint ignore=DL3013,DL3008
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        gcc gh jq curl openssl tar \
    && pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir pipenv \
    && pipenv lock \
    && pipenv install --system --deploy --categories packages \
    && pip uninstall -y pipenv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# hadolint ignore=DL3013,DL3008
RUN curl -sSL -O https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install --no-install-recommends -y azcopy \
    && echo "Checking installed azcopy version:" \
    && azcopy --version \
    && rm packages-microsoft-prod.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app/controller
CMD ["python3", "-m", "controller"]
