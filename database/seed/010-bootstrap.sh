#!/bin/sh
# Safe whether the official image executes or sources this mounted script.
(
  set -eu
  psql -X -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --file /database/seed/bootstrap.sql
)
