#!/bin/bash

# Copy javascript file to static directory of flower
to_path=$(find /usr/local -name flower.js)
cp -f /opt/home/custom-flower.js ${to_path}

# execute process by local user
exec su-exec user /sbin/tini -e 143 -- "$@"