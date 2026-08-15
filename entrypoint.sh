#!/bin/sh
set -e

flask --app 'app:create_app()' db upgrade
flask --app 'app:create_app()' seed-data
exec "$@"
