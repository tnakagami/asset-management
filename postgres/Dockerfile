ARG ARCHITECTURE=arm32v7

From ${ARCHITECTURE}/postgres:17-alpine3.21
ARG TZ=Asia/Tokyo

LABEL maintainer="tnakagami"
LABEL description="Build the environment of PostgreSQL"

RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata \
    && ln -s /usr/share/zoneinfo/${TZ} /etc/localtime
