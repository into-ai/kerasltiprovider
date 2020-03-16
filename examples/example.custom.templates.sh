#!/usr/bin/env bash

cd $(dirname $0)
docker-compose \
    -f ./example.custom.templates.yml \
    -f ./common/compose.tracing.yml \
    -f ./common/compose.redis.yml \
    "$@"