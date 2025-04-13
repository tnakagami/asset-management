ARG ARCHITECTURE=arm32v7

From ${ARCHITECTURE}/nginx:1.27-alpine3.21-perl
ARG TZ=Asia/Tokyo

LABEL maintainer="tnakagami"
LABEL description="Build the environment of Nginx"

COPY ./uwsgi_params /etc/nginx/uwsgi_params

RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata \
    && ln -s /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo -n > /etc/nginx/conf.d/default.conf