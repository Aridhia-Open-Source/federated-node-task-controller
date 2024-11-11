FROM python:3.12.2-alpine

COPY controller /app/controller
COPY --chmod=755 scripts/*.sh /app/scripts/
COPY Pipfile* /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# hadolint detects pipenv as another invocation of pip
# hadolint ignore=DL3013,DL3018
RUN apk --update --no-cache add gcc build-base github-cli jq curl openssl \
    && pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir pipenv \
    && pipenv lock \
    && pipenv install --system --deploy --categories packages \
    && pip uninstall -y pipenv

CMD ["python3", "-m", "controller"]
