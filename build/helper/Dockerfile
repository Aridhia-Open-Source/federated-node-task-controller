FROM alpine/k8s:1.29.4

ARG USERNAME=fednode
ARG USER_UID=1001
ARG USER_GID=1001

RUN addgroup -S "${USERNAME}" --gid "${USER_GID}" \
    && adduser -S "${USERNAME}" -G "${USERNAME}" -u "${USER_UID}"

# Can't find venv-related files
# hadolint ignore=SC1091
RUN apk add --no-cache \
        'jq=~1.7' \
        'curl=~8.5' \
        'openssl=~3.1' \
        'github-cli=~2.39' \
    && python3 -m venv venv \
    && . venv/bin/activate \
    && pip install --no-cache-dir "requests==2.32.3"

COPY . /app/
WORKDIR /app
USER ${USER_UID}

ENTRYPOINT [ "/apps/venv/bin/python3", "idp-init.py" ]
