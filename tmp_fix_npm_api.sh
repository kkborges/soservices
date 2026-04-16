#!/bin/sh
set -eu
docker exec nginx-proxy-manager sh -lc "sed -i 's/set \$server         \"nexus-frontend-ha\";/set \$server         \"nexus-api-ha\";/' /data/nginx/proxy_host/2.conf"
docker exec nginx-proxy-manager nginx -s reload
