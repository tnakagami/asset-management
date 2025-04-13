ARG ARCHITECTURE=arm32v7

From ${ARCHITECTURE}/python:3.12.10-alpine3.21
ARG TZ=Asia/Tokyo
ENV APP_ROOT_PATH=/code

COPY requirements.txt /requirements.txt

RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata libpq-dev pcre-dev libxml2-dev \
    \
    # Install temporary libraries
    \
    && apk add --no-cache --virtual .build-deps \
               gcc musl-dev libffi-dev g++ libgcc libstdc++ libxslt-dev \
               python3-dev libc-dev linux-headers openssl-dev curl shadow \
    && ln -s /usr/share/zoneinfo/${TZ} /etc/localtime \
    \
    # Install mandatory libraries
    \
    && pip install --upgrade pip setuptools \
    && pip install -r /requirements.txt \
    \
    # Create user
    \
    && useradd -s /sbin/nologin -M -d /dev/null django-user \
    \
    # Delete temporary libraries
    \
    && apk del .build-deps \
    && mkdir -p ${APP_ROOT_PATH} \
    && rm -rf /root/.cache /var/cache/apk/* /tmp/*

WORKDIR ${APP_ROOT_PATH}

EXPOSE 8001

CMD ["uwsgi", "--ini", "/uwsgi.ini"]
