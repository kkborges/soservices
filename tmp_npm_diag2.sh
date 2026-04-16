#!/bin/sh
set -eu
echo '--- proc names ---'
docker exec nginx-proxy-manager sh -c 'for p in /proc/[0-9]*; do printf "%s " "$(basename $p)"; cat $p/comm 2>/dev/null || true; done | head -80'
echo '--- nginx test ---'
docker exec nginx-proxy-manager sh -c 'nginx -t || true'
echo '--- proxy host snippets ---'
docker exec nginx-proxy-manager sh -c 'for f in /data/nginx/proxy_host/*.conf; do echo ===$f===; sed -n "1,80p" $f; done'
