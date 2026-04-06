# Software Bill of Materials (SBOM)

minecraftDash — Stand: 2026-04-06

---

## Inhaltsverzeichnis

- [Docker-Images](#docker-images)
- [Minecraft-Plugin](#minecraft-plugin)
- [Laufzeitabhängigkeiten (Homepage)](#laufzeitabhängigkeiten-homepage)
- [Skript-Laufzeitumgebungen](#skript-laufzeitumgebungen)
- [Entwicklungs- und Betriebswerkzeuge](#entwicklungs--und-betriebswerkzeuge)

---

## Docker-Images

| Komponente | Image | Version | Lizenz | Quelle |
|-----------|-------|---------|--------|--------|
| Prometheus | `prom/prometheus` | latest (2.x) | Apache 2.0 | [github.com/prometheus/prometheus](https://github.com/prometheus/prometheus) |
| Grafana | `grafana/grafana` | latest (12.x) | AGPL 3.0 | [github.com/grafana/grafana](https://github.com/grafana/grafana) |
| Caddy | `caddy:2-alpine` | 2.x (Alpine) | Apache 2.0 | [github.com/caddyserver/caddy](https://github.com/caddyserver/caddy) |

> **Hinweis:** `latest`-Tags werden beim `docker compose pull` auf die jeweils aktuelle stabile Version aufgelöst. Für reproduzierbare Deployments können die Tags auf konkrete Versionen (z. B. `prom/prometheus:v2.51.0`) fixiert werden.

---

## Minecraft-Plugin

| Komponente | Datei | Version | Lizenz | Quelle |
|-----------|-------|---------|--------|--------|
| minecraft-prometheus-exporter | `spigot/minecraft-prometheus-exporter.jar` | 3.1.2 | Apache 2.0 | [github.com/sladkoff/minecraft-prometheus-exporter](https://github.com/sladkoff/minecraft-prometheus-exporter) |

Wird in die Spigot-Docker-Images (minecraftHostingServer) eingebunden und läuft auf jedem überwachten Minecraft-Server. Exponiert Metriken auf Port `9940`.

---

## Laufzeitabhängigkeiten (Homepage)

Die Homepage (`homepage/index.html`) läuft vollständig im Browser ohne externe Bibliotheken. Alle Abhängigkeiten sind zur Laufzeit über den Browser selbst bereitgestellt.

| Komponente | Version | Bezug |
|-----------|---------|-------|
| Fetch API | Browser-nativ | Für Prometheus-HTTP-Abfragen |
| JSON | Browser-nativ | Für `servers.json` und Prometheus-Antworten |

Keine npm-Pakete, keine CDN-Abhängigkeiten — die Homepage funktioniert vollständig offline (solange Prometheus erreichbar ist).

---

## Skript-Laufzeitumgebungen

### update-server-names.py

| Abhängigkeit | Version | Bezug | Zweck |
|-------------|---------|-------|-------|
| Python | ≥ 3.6 | System | Laufzeitumgebung |
| `json` | stdlib | Python stdlib | Lesen/Schreiben von servers.json |
| `re` | stdlib | Python stdlib | Regex für YAML-Parsing und Farbcode-Entfernung |
| `subprocess` | stdlib | Python stdlib | `docker ps` / `docker exec` aufrufen |
| `os` | stdlib | Python stdlib | Pfadoperationen |
| Docker CLI | beliebig | System | Container-Zugriff |

Keine externen Pip-Pakete erforderlich.

### setup.sh

| Abhängigkeit | Version | Bezug | Zweck |
|-------------|---------|-------|-------|
| bash | ≥ 4.0 | System | Laufzeitumgebung |
| docker | beliebig | System | `docker compose`, `docker rm` |

---

## Entwicklungs- und Betriebswerkzeuge

Diese Werkzeuge sind nicht Teil des ausgelieferten Produkts, werden aber für Betrieb und Entwicklung benötigt.

| Werkzeug | Zweck |
|---------|-------|
| Docker Engine | Container-Laufzeitumgebung |
| Docker Compose (v2) | Multi-Container-Orchestrierung |
| Git | Versionsverwaltung |
| curl | Plugin- und Prometheus-Tests |
| iptables / netfilter-persistent | Firewall-Regeln für DOCKER-USER-Chain |
| cron | Stündliche Ausführung von `update-server-names.py` |
