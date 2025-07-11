FROM alpine/k8s:1.33.2

ARG USERNAME=fednode
ARG USER_UID=1001
ARG USER_GID=1001

RUN addgroup -S "${USERNAME}" --gid "${USER_GID}" \
    && adduser -S "${USERNAME}" -G "${USERNAME}" -u "${USER_UID}"

WORKDIR /apps
# Can't find venv-related files
# hadolint ignore=SC1091
RUN apk add --no-cache \
        'openssl=~3.1' \
        'github-cli=~2.39' \
    && python3 -m venv venv \
    && . venv/bin/activate \
    && pip install --no-cache-dir "requests==2.32.3" \
    && chown "${USER_UID}:${USER_GID}" /apps

COPY . /apps/
USER ${USER_UID}

ENV PATH="/apps/venv/bin:$PATH"
ENTRYPOINT [ "python3", "idp-init.py" ]
