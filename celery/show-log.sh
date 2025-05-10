#!/bin/bash

readonly _log_dir=/opt/home/celery/log

ls ${_log_dir}/celery*.log | while read log_file; do
  echo ${log_file}
  cat ${log_file}
  echo
done