FROM python:3.12.2-alpine

COPY controller /app/controller
COPY --chmod=755 scripts/tests/*.sh /app/scripts/
COPY Pipfile* /app

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# hadolint detects pipenv as another invocation of pip
# hadolint ignore=DL3013,DL3018
RUN apk --update --no-cache add gcc \
&& pip install --no-cache-dir --upgrade pip \
&& python3 -m pip install --no-cache-dir pipenv \
&& pipenv lock \
&& pipenv install --system --deploy --categories "packages dev" \
&& pip uninstall -y pipenv

ENV PYTHONPATH=/app/controller
CMD ["/app/scripts/test-entrypoint.sh"]
