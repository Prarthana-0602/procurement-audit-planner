#!/bin/sh
# Fly mounts the volume at /data owned by root: hand it to the app user, then drop privileges.
set -e
mkdir -p /data/runs /data/home
chown -R 1000:1000 /data
export HOME=/data/home
exec setpriv --reuid=1000 --regid=1000 --init-groups python -m harness
