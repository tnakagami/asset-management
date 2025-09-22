#!/bin/bash

is_running=1

# Setup handler
handler(){
  echo sigterm accepted

  is_running=0
}
trap handler 1 2 3 15

# Create pid directory and log directory
readonly _workdir=/opt/app
readonly _celery_root_dir=/opt/home/celery
readonly _pid_dir=${_celery_root_dir}/run
readonly _log_dir=${_celery_root_dir}/log
mkdir -p ${_pid_dir}
mkdir -p ${_log_dir}

# =============
# = Main loop =
# =============
celery multi start \
       --app=config --workdir=${_workdir} \
       worker --concurrency=${NUM_CPUS} --loglevel=INFO \
       --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER} \
       --pidfile="${_pid_dir}/celeryd-%n.pid" \
       --logfile="${_log_dir}/celeryd-%n%I.log"
celery --app=config --workdir=${_workdir} \
       beat --detach --loglevel=INFO --schedule ${_pid_dir}/celerybeat-schedule \
       --pidfile="${_pid_dir}/celery-beatd.pid" \
       --logfile="${_log_dir}/celery-beatd.log"

is_waiting=1
while [ ${is_waiting} -eq 1 ]; do
  num_workers=$(celery --app=config --workdir=${_workdir} inspect active 2> /dev/null | grep -oE "worker.*?: OK" | wc -l)

  if [ ${num_workers} -gt 0 ]; then
    is_waiting=0
  fi
done
# Start flower
celery --app=config --workdir=${_workdir} \
       flower --address=0.0.0.0 --port=5053 --url_prefix=flower --purge_offline_workers=60 \
       --max_workers=${CELERY_WORKER_PREFETCH_MULTIPLIER} --max_tasks=128 \
       --log_file_max_size=$(expr 3 \* 1024 \* 1024) --log_file_num_backups=3 \
       --log_file_prefix=${_log_dir}/celery-flower.log --logging=info &
flower_pid=$!

while [ ${is_running} -eq 1 ]; do
  sleep 1
done

# Finalize
kill ${flower_pid}
{
  ls ${_pid_dir}/celery-beatd.pid
  ls ${_pid_dir}/celeryd-*.pid
} | while read pid_file; do
  pid=$(cat ${pid_file})
  kill ${pid}
done