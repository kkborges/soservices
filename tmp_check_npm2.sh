#!/bin/sh
set -eu
printf '== data files ==\n'
docker exec nginx-proxy-manager sh -lc 'ls -R /data | sed -n "1,260p"'
printf '\n== proxy host configs ==\n'
docker exec nginx-proxy-manager sh -lc 'for f in /data/nginx/proxy_host/*.conf; do echo "--- $f ---"; sed -n "1,220p" "$f"; done'
