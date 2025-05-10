#!/bin/sh

is_running=1

# Setup handler
handler(){
  echo sigterm accepted

  is_running=0
}
trap handler 1 2 3 15

# Set overcommit
sysctl vm.overcommit_memory=1
# Run redis server
redis-server /usr/local/etc/redis/redis.conf --daemonize yes --loglevel warning --bind 0.0.0.0

while [ ${is_running} -eq 1 ]; do
  sleep 1
done