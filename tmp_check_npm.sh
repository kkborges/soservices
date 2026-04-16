#!/bin/sh
set -eu
printf '== proxy_host ==\n'
docker exec nginx-proxy-manager sh -lc "sqlite3 /data/database.sqlite \"select id,domain_names,forward_host,forward_port,enabled from proxy_host order by id;\""
printf '\n== nginx conf ==\n'
docker exec nginx-proxy-manager sh -lc 'nginx -T 2>/dev/null | sed -n "1,260p"'
