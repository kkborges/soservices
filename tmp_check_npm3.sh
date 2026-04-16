#!/bin/sh
set -eu
docker exec nginx-proxy-manager sh -lc 'for f in /data/nginx/proxy_host/*.conf; do echo ---:$f:---; cat "$f"; echo; done'
