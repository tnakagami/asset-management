ARG ARCHITECTURE=arm32v7

From ${ARCHITECTURE}/python:3.12.10-alpine3.21
ARG UID
ARG GID
ARG USERNAME=user
ARG GROUPNAME=user
ARG TZ=Asia/Tokyo
ENV APP_ROOT_PATH=/opt/app

LABEL maintainer="tnakagami"
LABEL description="Build the environment of Django application"

COPY ./pyproject.toml /opt/pyproject.toml
COPY ./tester.sh /opt/tester.sh

RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata libmagic libpq-dev pcre-dev libxml2-dev gettext \
    \
    # Install temporary libraries
    \
    && apk add --no-cache --virtual .build-deps \
               gcc musl-dev libffi-dev g++ libgcc libstdc++ libxslt-dev \
               python3-dev libc-dev linux-headers openssl-dev cargo curl shadow \
    && ln -s /usr/share/zoneinfo/${TZ} /etc/localtime \
    && pip install --upgrade pip setuptools \
    && pip install poetry \
    \
    # Create user
    \
    && groupadd -g ${GID} ${GROUPNAME} \
    && useradd \
         --no-log-init \
         --shell /bin/bash \
         --create-home --home-dir /opt/home \
         --gid ${GID} --uid ${UID} \
         ${USERNAME} \
    && mkdir -p ${APP_ROOT_PATH} \
    && chown -R ${USERNAME}:${GROUPNAME} /opt/home /opt/tester.sh \
    && chmod 755 /opt/tester.sh

RUN   cd /opt \
    \
    # Install mandatory libraries
    \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi \
    && cd / \
    \
    # Delete temporary libraries
    \
    && apk del .build-deps \
    && chown -R ${USERNAME}:${GROUPNAME} /opt/poetry.lock \
    && rm -rf /root/.cache /var/cache/apk/* /tmp/*

WORKDIR ${APP_ROOT_PATH}
USER ${USERNAME}

EXPOSE 8001

CMD ["uwsgi", "--ini", "/opt/uwsgi.ini"]
