#!/bin/bash

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

  cleanup
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
      docker-compose build --no-cache
      clean_up

      shift
      ;;

    start )
      docker-compose up -d

      shift
      ;;

    stop | restart | down | ps )
      docker-compose $1

      shift
      ;;

    logs )
      docker-compose logs -t | sort -t "|" -k 1,+2d

      shift
      ;;

    cleanup )
      clean_up

      shift
      ;;

    * )
      shift
      ;;
  esac
done
