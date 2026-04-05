#!/usr/bin/env bash
# setup.sh — minecraftDash Stack konfigurieren und starten
#
# Beispiele:
#   ./setup.sh                                   # nur Core (Prometheus + Grafana)
#   ./setup.sh --caddy                           # + Caddy (HTTP)
#   ./setup.sh --caddy --homepage                # + Caddy + Homepage (HTTP)
#   ./setup.sh --caddy --homepage --domain example.com  # + HTTPS via Let's Encrypt
#   ./setup.sh --down                            # Stack stoppen

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
OPT_CADDY=false
OPT_HOMEPAGE=false
OPT_DOMAIN=""
OPT_DOWN=false
OPT_DRYRUN=false

# ── Argument parsing ───────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --caddy              Caddy Reverse Proxy einbinden (HTTP auf Port 80/443)
  --homepage           Homepage einbinden (benötigt --caddy)
  --domain DOMAIN      HTTPS aktivieren: Caddy holt automatisch ein TLS-Zertifikat
                       (benötigt --caddy; setzt --homepage implizit)
  --down               Stack stoppen (docker compose down)
  --dry-run            Zeigt den generierten docker compose-Befehl, führt ihn aber nicht aus
  -h, --help           Diese Hilfe anzeigen

Beispiele:
  ./setup.sh
  ./setup.sh --caddy
  ./setup.sh --caddy --homepage
  ./setup.sh --caddy --homepage --domain minecraft.example.com
  ./setup.sh --down
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --caddy)      OPT_CADDY=true ;;
    --homepage)   OPT_HOMEPAGE=true ;;
    --domain)
      shift
      if [[ -z "${1:-}" ]]; then
        echo "Fehler: --domain erwartet einen Wert" >&2; exit 1
      fi
      OPT_DOMAIN="$1"
      OPT_CADDY=true
      OPT_HOMEPAGE=true
      ;;
    --down)       OPT_DOWN=true ;;
    --dry-run)    OPT_DRYRUN=true ;;
    -h|--help)    usage; exit 0 ;;
    *)            echo "Unbekannte Option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if $OPT_HOMEPAGE && ! $OPT_CADDY; then
  echo "Fehler: --homepage benötigt --caddy" >&2; exit 1
fi

# ── Caddyfile schreiben ────────────────────────────────────────────────────────
write_caddyfile() {
  local caddyfile="$(dirname "$0")/Caddyfile"

  if [[ -n "$OPT_DOMAIN" ]]; then
    cat > "$caddyfile" <<EOF
# Automatisch generiert von setup.sh — nicht manuell bearbeiten
$OPT_DOMAIN {
	root * /srv
	file_server

	handle_path /api/prometheus/* {
		reverse_proxy prometheus:9090
	}
}
EOF
    echo "  Caddyfile → HTTPS für $OPT_DOMAIN"
  else
    cat > "$caddyfile" <<'EOF'
# Automatisch generiert von setup.sh — nicht manuell bearbeiten
:80 {
	root * /srv
	file_server

	handle_path /api/prometheus/* {
		reverse_proxy prometheus:9090
	}
}
EOF
    echo "  Caddyfile → HTTP (:80)"
  fi
}

# ── docker compose-Befehl zusammenbauen ───────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILES=("-f" "docker-compose.yml")
$OPT_CADDY     && COMPOSE_FILES+=("-f" "compose.caddy.yml")
$OPT_HOMEPAGE  && COMPOSE_FILES+=("-f" "compose.homepage.yml")

if $OPT_DOWN; then
  CMD=(docker compose "${COMPOSE_FILES[@]}" down)
else
  CMD=(docker compose "${COMPOSE_FILES[@]}" up -d)
fi

# ── Zusammenfassung ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  minecraftDash Setup"
echo "══════════════════════════════════════════"
echo "  Core (Prometheus + Grafana):  ✓"
printf "  Caddy Reverse Proxy:          %s\n" "$($OPT_CADDY && echo "✓" || echo "–")"
printf "  Homepage:                     %s\n" "$($OPT_HOMEPAGE && echo "✓" || echo "–")"
if [[ -n "$OPT_DOMAIN" ]]; then
  echo "  HTTPS Domain:                 $OPT_DOMAIN"
else
  $OPT_CADDY && echo "  HTTP:                         :80"
fi
echo "──────────────────────────────────────────"
echo "  Befehl: ${CMD[*]}"
echo "══════════════════════════════════════════"
echo ""

if $OPT_DRYRUN; then
  echo "(--dry-run: wird nicht ausgeführt)"
  exit 0
fi

# Caddyfile nur schreiben wenn Caddy aktiv und kein --down
if $OPT_CADDY && ! $OPT_DOWN; then
  write_caddyfile
fi

# Docker hat einen bekannten Timing-Bug: das Default-Netzwerk wird angelegt,
# aber der letzte Container findet es kurz nicht. Einmal wiederholen reicht.
if ! "${CMD[@]}"; then
  echo ""
  echo "Erster Versuch fehlgeschlagen (Docker-Netzwerk-Bug), starte neu..."
  sleep 1
  "${CMD[@]}"
fi

# ── Erreichbarkeit ausgeben ────────────────────────────────────────────────────
if ! $OPT_DOWN; then
  echo ""
  echo "Dienste erreichbar unter:"
  if [[ -n "$OPT_DOMAIN" ]]; then
    echo "  Homepage   → https://$OPT_DOMAIN"
    echo "  Grafana    → http://localhost:3000  (admin / admin)"
    echo "  Prometheus → http://localhost:9090"
  elif $OPT_CADDY; then
    echo "  Homepage   → http://localhost"
    echo "  Grafana    → http://localhost:3000  (admin / admin)"
    echo "  Prometheus → http://localhost:9090"
  else
    echo "  Grafana    → http://localhost:3000  (admin / admin)"
    echo "  Prometheus → http://localhost:9090"
  fi
fi
