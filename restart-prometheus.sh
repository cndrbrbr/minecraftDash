#!/bin/bash
# Prometheus neu starten und Scrape-Status anzeigen

COMPOSE_FILE="$(dirname "$0")/docker-compose.yml"

if docker info &>/dev/null; then
  docker compose -f "$COMPOSE_FILE" restart prometheus
else
  sg docker "docker compose -f '$COMPOSE_FILE' restart prometheus"
fi

echo ""
echo "Warte auf Prometheus..."
sleep 10

echo ""
echo "Server-Status:"
curl -s -G "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=up{job="minecraft"}' | \
  python3 -c "
import sys, json
d = json.load(sys.stdin)
results = d['data']['result']
if not results:
    print('  Keine Targets gefunden.')
else:
    for r in results:
        name = r['metric'].get('server_name', r['metric'].get('instance', '?'))
        status = 'UP  ✔' if r['value'][1] == '1' else 'DOWN ✘'
        print(f'  {name:<20} {status}')
"
