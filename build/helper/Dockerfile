FROM python:3.12-alpine3.19

ARG USERNAME=fednode
ARG USER_UID=1001
ARG USER_GID=1001

RUN addgroup -S "${USERNAME}" --gid "${USER_GID}" \
    && adduser -S "${USERNAME}" -G "${USERNAME}" -u "${USER_UID}"

RUN python -m pip install requests

COPY idp-init.py /scripts/idp-init.py

WORKDIR /scripts
USER ${USER_UID}

ENTRYPOINT [ "python3", "config.py" ]
