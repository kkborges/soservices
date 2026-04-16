#!/bin/sh
set -eu
echo '--- ps ---'
docker exec nginx-proxy-manager sh -c 'ps aux'
echo '--- nginx test ---'
docker exec nginx-proxy-manager sh -c 'nginx -t || true'
echo '--- listeners inside ---'
docker exec nginx-proxy-manager sh -c 'ss -lntp || netstat -lntp || true'
echo '--- proxy host snippets ---'
docker exec nginx-proxy-manager sh -c 'for f in /data/nginx/proxy_host/*.conf; do echo ===$f===; sed -n "1,80p" $f; done'
