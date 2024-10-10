FROM python:3.12.2-alpine

COPY controller /app/controller
COPY --chmod=755 scripts/jwt.sh /app/scripts/
COPY --chmod=755 scripts/push_to_github.sh /app/scripts/
COPY Pipfile* /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

RUN apk --update add gcc build-base github-cli jq curl openssl \
    && pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir pipenv \
    && pipenv lock \
    && pipenv install --system --deploy --categories packages \
    && pip uninstall -y pipenv

CMD ["python3", "-m", "controller"]
