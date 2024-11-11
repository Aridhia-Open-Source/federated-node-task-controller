FROM python:3.12.2-alpine

COPY controller /app/controller
COPY --chmod=755 scripts/tests/test-entrypoint.sh /app/scripts/test-entrypoint.sh
COPY Pipfile* /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

RUN apk --update add gcc \
&& pip install --no-cache-dir --upgrade pip \
&& python3 -m pip install --no-cache-dir pipenv \
&& pipenv lock \
&& pipenv install --system --deploy --categories "packages dev" \
&& pip uninstall -y pipenv

WORKDIR /app/controller
ENV PYTHONPATH=/app/controller
CMD ["/app/scripts/test-entrypoint.sh"]
