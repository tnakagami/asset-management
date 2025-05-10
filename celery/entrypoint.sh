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

while [ ${is_running} -eq 1 ]; do
  sleep 1
done

# Finalize
{
  ls ${_pid_dir}/celery-beatd.pid
  ls ${_pid_dir}/celeryd-*.pid
} | while read pid_file; do
  pid=$(cat ${pid_file})
  kill ${pid}
done