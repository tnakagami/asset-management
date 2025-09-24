#!/bin/bash

is_running=1

# Setup handler
handler(){
  echo sigterm accepted

  is_running=0
}
trap handler 1 2 3 15

readonly CELERY_CMD_WITH_OPTS="celery --app=config --workdir=/opt/app"

# =============
# = Main loop =
# =============
is_waiting=1
while [ ${is_running} -eq 1 ] && [ ${is_waiting} -eq 1 ]; do
  sleep 1
  num_workers=$(${CELERY_CMD_WITH_OPTS} inspect active 2> /dev/null | grep -oE "worker.*?: OK" | wc -l)

  if [ ${num_workers} -gt 0 ]; then
    is_waiting=0
  fi
done
# Run flower
${CELERY_CMD_WITH_OPTS} flower --log_to_stderr &
pid=$!

while [ ${is_running} -eq 1 ]; do
  sleep 1
done

# Finalize
kill ${pid}