FROM alpine/k8s:1.33.2

ARG USERNAME=fednode
ARG USER_UID=1001
ARG USER_GID=1001

RUN addgroup -S "${USERNAME}" --gid "${USER_GID}" \
    && adduser -S "${USERNAME}" -G "${USERNAME}" -u "${USER_UID}"

WORKDIR /apps
# Can't find venv-related files
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
# hadolint ignore=SC1091
RUN apk add --no-cache \
        'jq=~1.8.0' \
        'openssl=~3.5.2' \
        'github-cli=~2.72.0' \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /root/.local/bin/uv init \
    && /root/.local/bin/uv add requests \
    && chown "${USER_UID}:${USER_GID}" /apps

COPY . /apps/
USER ${USER_UID}

ENV PATH="/apps/.venv/bin:$PATH"
ENTRYPOINT [ "python3", "idp-init.py" ]
