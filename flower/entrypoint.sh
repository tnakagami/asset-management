#!/bin/bash

# Copy javascript file to static directory of flower
to_path=$(find /usr/local -name flower.js)
cp -f /opt/home/custom-flower.js ${to_path}

# Install command
   apk update \
&& apk upgrade \
&& apk add --no-cache su-exec tini \
&& rm -rf /root/.cache /var/cache/apk/* /tmp/*

# execute process by local user
exec su-exec user /sbin/tini -e 143 -- "$@"