set -eu
cd /srv/las-platform/docker
docker rm -f nexus-api-a nexus-api-b nexus-frontend-ha
docker-compose -f docker-compose.ha.yml up -d --build nexus-api-a nexus-api-b nexus-api-ha nexus-frontend-ha
sleep 20
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'nexus-api|nexus-frontend|NAMES'