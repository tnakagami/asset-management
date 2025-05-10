ARG ARCHITECTURE=arm32v7
FROM ${ARCHITECTURE}/redis:8-alpine

LABEL maintainer="tnakagami"
LABEL description="build redis environment"

# Copy shell script
COPY ./init.sh /init.sh

# To store redis's config file
RUN    mkdir -p /usr/local/etc/redis \
    && mkdir -p /var/log/redis \
    && chmod +x /init.sh \
    && echo -n > /usr/local/etc/redis/redis.conf

EXPOSE 6379

CMD ["/init.sh"]