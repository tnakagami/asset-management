#!/bin/bash

readonly DJANGO_CONTAINER_NAME=django.asset-management

function Usage() {
cat <<- _EOF
Usage: $0 command [option] ...

Enabled commands:
  build
    Build docker image using Dockerfile

  start
    Start all containers

  stop
    Stop all containers

  restart
    Restart all containers

  down
    Destroy all containers

  ps
    Show the running containers

  logs
    Show logs of each container

  migrate
    Execute database migration of Django in the docker environment

  loaddata
    Load yaml data to Django's database

  test
    Execute pytest

  cleanup [-f]
    Delete invalid containers and images

  help | -h
    Show this message
_EOF
}

function clean_up() {
  # Delete disabled containers
  docker ps -a | grep Exited | awk '{print $1;}' | xargs -I{} docker rm -f {}
  # Delete disabled images
  docker images | grep none | awk '{print $3;}' | xargs -I{} docker rmi {}
}

# ================
# = main routine =
# ================

if [ $# -eq 0 ]; then
  Usage
  exit 0
fi

while [ -n "$1" ]; do
  case "$1" in
    help | -h )
      Usage

      shift
      ;;

    build )
      docker-compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
      clean_up

      shift
      ;;

    start )
      docker-compose up -d

      shift
      ;;

    stop | restart | down )
      docker-compose $1

      shift
      ;;

    ps )
      docker-compose ps | sed -r -e "s|\s{2,}|#|g" | awk -F'[#]' '
      BEGIN {
        maxlen_service = -1;
        maxlen_status = -1;
        maxlen_port = -1;
      }
      FNR > 1{
        _services[FNR] = $3;
        _statuses[FNR] = $4;
        _ports[FNR] = $5;
        service_len = length($3);
        status_len = length($4);
        port_len = length($5);

        if (maxlen_service < service_len) { maxlen_service = service_len; }
        if (maxlen_status < status_len) { maxlen_status = status_len; }
        if (maxlen_port < port_len) { maxlen_port = port_len; }
      }
      END {
        if (FNR > 1) {
          total_len = maxlen_service + maxlen_status + maxlen_port;
          hyphens = sprintf("%*s", total_len + 9, "");
          gsub(".", "-", hyphens);
          # Output
          printf("%-*s | %-*s | %-*s\n", maxlen_service, "Service", maxlen_status, "Status", maxlen_port, "Port");
          print hyphens;

          for (idx = 2; idx <= FNR; idx++) {
            printf("%*s | %*s | %-*s\n",
              maxlen_service, _services[idx],
              maxlen_status, _statuses[idx],
              maxlen_port, _ports[idx]);
          }
        }
      }'

      shift
      ;;

    logs )
      docker-compose logs -t | sort -t "|" -k 1,+2d

      shift
      ;;

    migrate )
      docker-compose up -d
      apps=$(find django/src -type f | grep -oP "(?<=/)([a-zA-Z]+)(?=/apps.py$)" | tr '\n' ' ')
      commands="python manage.py makemigrations ${apps}; python manage.py migrate"
      docker exec ${DJANGO_CONTAINER_NAME} bash -c "${commands}"

      shift
      ;;

    loaddata )
      docker-compose up -d
      xml_file_path='stock/fixtures/${DJANGO_LANGUAGE_CODE}/*.yaml'
      docker exec ${DJANGO_CONTAINER_NAME} bash -c "python manage.py loaddata ${xml_file_path}"

      shift
      ;;

    test )
      docker-compose up -d
      docker ${DJANGO_CONTAINER_NAME} /opt/tester.sh

      shift
      ;;

    cleanup )
      clean_up
      shift

      if [ "$1" = "-f" ]; then
        docker builder prune -f
        shift
      fi
      ;;

    * )
      shift
      ;;
  esac
done
