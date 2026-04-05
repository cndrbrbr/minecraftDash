# minecraftDash

Zentrale Überwachung mehrerer Minecraft-Server mit Prometheus, Grafana und Discord-Alerts.
Optional mit Caddy als Reverse Proxy (HTTP/HTTPS) und einer Server-Übersichts-Homepage.

## Inhalt

- [Architektur](#architektur)
- [Voraussetzungen](#voraussetzungen)
- [Einrichtung](#einrichtung)
- [Setup-Script](#setup-script)
- [Deployment-Modi](#deployment-modi)
- [Homepage](#homepage--server-karten)
- [Minecraft-Server einrichten](#minecraft-server-einrichten)
- [Weiteren Server hinzufügen](#weiteren-server-hinzufügen)
- [HTTPS einrichten](#https-einrichten)
- [Discord-Alerts einrichten](#discord-alerts-einrichten)
- [Grafana-Dashboard](#grafana-dashboard)
- [Firewall (iptables)](#firewall-iptables)
- [Verzeichnisstruktur](#verzeichnisstruktur)
- [Nützliche Befehle](#nützliche-befehle)

---

## Architektur

```
Minecraft Server 1  ──┐
  (Plugin :9940)      │
                      ▼
Minecraft Server 2  ──▶  Prometheus  ──▶  Grafana  ──▶  Discord
  (Plugin :9940)      │   (:9090)          (:3000)       (Alerts)
                      │
Minecraft Server N  ──┘       ▲
  (Plugin :9940)               │
                          Caddy (:80/:443)
                          └── Homepage (Server-Übersicht)
                          └── Prometheus API Proxy
```

Auf jedem Minecraft-Server läuft das Plugin **minecraft-prometheus-exporter**, das Metriken (Spieleranzahl, TPS, RAM, Entities u. v. m.) über HTTP bereitstellt. Prometheus sammelt diese Daten zentral ein. Grafana visualisiert sie und sendet Alerts an Discord. Die Homepage zeigt alle Metriken live als Server-Karten an.

---

## Voraussetzungen

- Docker + Docker Compose
- Netzwerkzugriff vom Monitoring-Server zu Port `9940` aller Minecraft-Server

---

## Einrichtung

### 1. Repository klonen

```bash
git clone https://github.com/cndrbrbr/minecraftDash.git
cd minecraftDash
```

### 2. Server eintragen

`prometheus.yml` öffnen und Minecraft-Server als Targets eintragen:

```yaml
scrape_configs:
  - job_name: "minecraft"
    static_configs:
      - targets: ["185.170.113.136:9941"]
        labels:
          server_name: "mc1"

      - targets: ["185.170.113.136:9942"]
        labels:
          server_name: "mc2"
```

### 3. Discord-Webhook eintragen (optional)

`grafana/provisioning/alerting/contactpoints.yaml` öffnen:

```yaml
settings:
  url: "https://discord.com/api/webhooks/DEINE_WEBHOOK_URL"
```

### 4. Stack starten

Gewünschten [Deployment-Modus](#deployment-modi) wählen und starten, oder das [Setup-Script](#setup-script) verwenden.

---

## Setup-Script

`setup.sh` nimmt alle Optionen als Parameter entgegen, schreibt das `Caddyfile` automatisch und startet den passenden Stack.

```bash
./setup.sh [OPTIONS]
```

| Option | Beschreibung |
|--------|-------------|
| _(keine)_ | Core: Prometheus + Grafana |
| `--caddy` | Caddy Reverse Proxy einbinden (HTTP :80) |
| `--homepage` | Homepage einbinden (benötigt `--caddy`) |
| `--domain DOMAIN` | HTTPS aktivieren — Caddy holt automatisch ein Let's Encrypt-Zertifikat (setzt `--caddy` und `--homepage` implizit) |
| `--down` | Stack stoppen |
| `--dry-run` | Befehl anzeigen, nicht ausführen |

**Beispiele:**

```bash
# Nur Core
./setup.sh

# Mit Caddy (HTTP)
./setup.sh --caddy

# Mit Caddy + Homepage
./setup.sh --caddy --homepage

# Mit HTTPS (Caddy + Homepage + Let's Encrypt)
./setup.sh --domain minecraft.example.com

# Stack stoppen
./setup.sh --down
```

Das Script gibt nach dem Start die URLs aller Dienste aus.

---

## Deployment-Modi

Der Stack ist parametrisiert — Caddy und Homepage sind optional zuschaltbar.
> **Tipp:** Statt der folgenden `docker compose`-Befehle kann auch das [Setup-Script](#setup-script) verwendet werden.

### Modus 1 — Core (Prometheus + Grafana)

```bash
docker compose up -d
```

| Dienst     | URL                   | Zugangsdaten  |
|------------|-----------------------|---------------|
| Grafana    | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | —             |

### Modus 2 — Core + Caddy (HTTP/HTTPS Reverse Proxy)

```bash
docker compose -f docker-compose.yml -f compose.caddy.yml up -d
```

| Dienst     | URL                   |
|------------|-----------------------|
| Caddy      | http://localhost      |
| Grafana    | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

### Modus 3 — Core + Caddy + Homepage

```bash
docker compose -f docker-compose.yml -f compose.caddy.yml -f compose.homepage.yml up -d
```

| Dienst     | URL                   |
|------------|-----------------------|
| Homepage   | http://localhost      |
| Grafana    | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

Die Homepage zeigt eine Live-Übersicht aller Server und enthält die Projektdokumentation.

### Homepage — Server-Karten

Jede Server-Karte zeigt alle verfügbaren Prometheus-Metriken:

| Bereich | Metriken |
|---------|---------|
| Header | Anzeigename (MOTD / servers.json / server_name), Version, Online-Badge |
| Spieler & Performance | Spieler online, TPS (farbig: grün ≥18, gelb ≥15, rot <15), RAM benutzt / max |
| Welt | Geladene Chunks, Entities, Whitelist-Einträge |
| Tick-Timing | Median, Durchschnitt, Min, Max (in ms) |
| JVM | Threads, GC-Events, Weltgröße |

Die globale Zusammenfassung oben zeigt: Server online/offline, Spieler gesamt, Ø TPS, Entities gesamt.

### Homepage — Anzeigenamen konfigurieren

Der Anzeigename einer Server-Karte wird in dieser Priorität ermittelt:

1. **MOTD** aus `mc_server_info` (automatisch, wenn im Plugin aktiviert — empfohlen)
2. **`homepage/servers.json`** (manuelle Konfiguration als Fallback)
3. **`server_name`**-Label aus `prometheus.yml`

`homepage/servers.json` bearbeiten um manuelle Namen zu setzen:

```json
{
  "mm-lobby": "Lobby",
  "mm-mc1":   "Welt 1",
  "mm-mc2":   "Welt 2"
}
```

Für automatische MOTD-Anzeige muss `server_info: true` in der Plugin-Konfiguration gesetzt sein (siehe [Plugin konfigurieren](#2-plugin-konfigurieren)).

---

## Minecraft-Server einrichten

Das Plugin muss auf **jedem** zu überwachenden Minecraft-Server installiert werden.

### 1. Plugin installieren

Plugin herunterladen und in den `plugins/`-Ordner des Servers legen:

```
plugins/
└── minecraft-prometheus-exporter-3.1.2.jar
```

Download: [github.com/sladkoff/minecraft-prometheus-exporter/releases](https://github.com/sladkoff/minecraft-prometheus-exporter/releases)

### 2. Plugin konfigurieren

Nach dem ersten Start erstellt das Plugin die Datei `plugins/PrometheusExporter/config.yml`.
Für maximale Metrik-Abdeckung (alle Felder aktivieren, MOTD für Homepage):

```yaml
host: 0.0.0.0
port: 9940
enable_metrics:
  server_info: true          # MOTD + Version → wird in der Homepage angezeigt
  entities_total: true
  villagers_total: true
  loaded_chunks_total: true
  jvm_memory: true
  players_online_total: true
  players_total: true
  whitelisted_players: true
  tps: true
  world_size: true
  jvm_threads: true
  jvm_gc: true
  tick_duration_median: true
  tick_duration_average: true
  tick_duration_min: true
  tick_duration_max: true
  player_online: true
  player_statistic: true
```

Server neu laden: `/reload` oder Neustart.

> **Hinweis:** Ohne `server_info: true` zeigt die Homepage den `server_name`-Label aus `prometheus.yml` bzw. den Eintrag aus `homepage/servers.json` als Anzeigenamen.

### 3. Firewall

Port `9940` muss vom Monitoring-Server aus erreichbar sein.
Der Port muss **nicht** öffentlich zugänglich sein — nur für Prometheus.

```bash
# Beispiel: ufw
ufw allow from <monitoring-server-ip> to any port 9940
```

---

## Weiteren Server hinzufügen

### Voraussetzungen auf dem Minecraft-Server

Bevor ein Server in Prometheus eingetragen wird, muss dort das Plugin laufen und von außen erreichbar sein.

Status prüfen:
```bash
curl http://<server-ip>:9940/metrics
```
Gibt die Seite Metriken zurück, ist der Server bereit.

---

### Szenario 1 — Externer Server (Internet)

**`prometheus.yml` ergänzen:**

```yaml
scrape_configs:
  - job_name: "minecraft"
    static_configs:
      - targets: ["mein-server.example.com:9940"]
        labels:
          server_name: "survival"
```

**Firewall auf dem Minecraft-Server:**
```bash
ufw allow from <monitoring-ip> to any port 9940
```

---

### Szenario 2 — Lokaler Server im selben Docker-Netzwerk

Der Server läuft als Docker-Container auf demselben Host (z. B. aus [minecraftHostingServer](https://github.com/cndrbrbr/minecraftHostingServer)).

Prometheus einmalig mit dem anderen Docker-Netzwerk verbinden:

```bash
docker network connect minecrafthostingserver_default prometheus
```

> Dauerhaft machen — in `docker-compose.yml` unter `prometheus` eintragen:
>
> ```yaml
> prometheus:
>   ...
>   networks:
>     - default
>     - minecrafthostingserver_default
>
> networks:
>   default:
>   minecrafthostingserver_default:
>     external: true
> ```

**`prometheus.yml` ergänzen** — Container-Name als Hostname:

```yaml
      - targets: ["mc1:9940"]
        labels:
          server_name: "mc1"
```

---

### Szenario 3 — Lokaler Server, Port nach außen gemappt

Port 9940 des Containers ist auf einen Host-Port gemappt (z. B. `9941:9940`).

```yaml
      - targets: ["host.docker.internal:9941"]
        labels:
          server_name: "mc1"
```

---

### Prometheus neu laden

Nach jeder Änderung an `prometheus.yml`:

```bash
docker compose restart prometheus
```

Das Grafana-Dashboard erkennt neue Server automatisch über die `server_name`-Variable.

---

## HTTPS einrichten

Caddy holt automatisch ein Let's Encrypt-Zertifikat sobald eine Domain konfiguriert ist.

### 1. Domain auf Server-IP zeigen lassen (DNS A-Record)

### 2. Caddyfile anpassen

Den kommentierten HTTPS-Block in `Caddyfile` aktivieren und Domain eintragen:

```
yourdomain.com {
    root * /srv
    file_server

    handle_path /api/prometheus/* {
        reverse_proxy prometheus:9090
    }
}
```

Den `:80`-Block entfernen oder behalten (Caddy leitet dann automatisch auf HTTPS um).

### 3. Caddy neu starten

```bash
docker compose -f docker-compose.yml -f compose.caddy.yml -f compose.homepage.yml restart caddy
```

---

## Discord-Alerts einrichten

### 1. Discord-Webhook erstellen

In Discord: **Servereinstellungen → Integrationen → Webhooks → Neuen Webhook erstellen**
Webhook-URL kopieren.

### 2. URL eintragen

Datei `grafana/provisioning/alerting/contactpoints.yaml` öffnen:

```yaml
settings:
  url: "https://discord.com/api/webhooks/DEINE_WEBHOOK_URL"
```

### 3. Grafana neu starten

```bash
docker compose restart grafana
```

### Vorkonfigurierte Alerts

| Alert          | Bedingung                             | Schwere  |
|----------------|---------------------------------------|----------|
| Server Down    | Server nicht erreichbar für 2 min     | critical |
| TPS zu niedrig | TPS < 15 für 5 min                    | warning  |

Weitere Alerts können in `grafana/provisioning/alerting/rules.yaml` ergänzt werden.

---

## Grafana-Dashboard

Das Dashboard **"Minecraft Dashboard"** wird automatisch unter dem Ordner **Minecraft** bereitgestellt.

### Panels

| Panel               | Beschreibung                          |
|---------------------|---------------------------------------|
| Spieler Online      | Aktuelle Gesamtzahl aller Spieler     |
| Server Online       | Anzahl erreichbarer Server            |
| TPS (Ø)             | Durchschnittliche Ticks pro Sekunde   |
| RAM Heap            | Aktueller Heap-Speicherverbrauch      |
| Spieler pro Server  | Zeitverlauf je Server                 |
| TPS pro Server      | TPS-Verlauf je Server                 |
| RAM pro Server      | Heap-Verbrauch und Maximum je Server  |

### Server-Filter

Oben im Dashboard befindet sich ein Dropdown **"Server"** zum Filtern auf einzelne oder mehrere Server. Neue Server erscheinen dort automatisch, sobald Prometheus sie scrapt.

---

## Firewall (iptables)

Docker-published Ports umgehen die `INPUT`-Chain. Regeln für Docker-Container gehören in die `DOCKER-USER`-Chain.

```bash
ADMIN_IP="<IP_DES_ADMINS>"   # z. B. 1.2.3.4

# ── Grafana (3000) — nur Admin ────────────────────────────────
iptables -A DOCKER-USER -p tcp --dport 3000 -s "$ADMIN_IP" -j ACCEPT
iptables -A DOCKER-USER -p tcp --dport 3000 -j DROP

# ── Prometheus (9090) — nur lokal / Admin ─────────────────────
iptables -A DOCKER-USER -p tcp --dport 9090 -s 127.0.0.1   -j ACCEPT
iptables -A DOCKER-USER -p tcp --dport 9090 -s "$ADMIN_IP" -j ACCEPT
iptables -A DOCKER-USER -p tcp --dport 9090 -j DROP

# ── Caddy (80/443) — öffentlich ───────────────────────────────
# Caddy selbst entscheidet, wer was sehen darf.
# Keine Einschränkung nötig — Port 80/443 muss offen sein.
```

> **Wichtig:** `-A` (append) statt `-I` (insert) verwenden — sonst landet DROP vor ACCEPT und alles wird geblockt.

**Regeln dauerhaft speichern** (Debian/Ubuntu):
```bash
apt install iptables-persistent
netfilter-persistent save
```

**Regeln prüfen:**
```bash
iptables -L DOCKER-USER -n --line-numbers
```

---

## Verzeichnisstruktur

```
minecraftDash/
├── docker-compose.yml                        # Core-Stack (Prometheus + Grafana)
├── compose.caddy.yml                         # Opt-in: Caddy Reverse Proxy
├── compose.homepage.yml                      # Opt-in: Homepage (benötigt compose.caddy.yml)
├── Caddyfile                                 # Caddy-Konfiguration (HTTP + HTTPS-Vorlage)
├── setup.sh                                  # Setup-Script (Parameter: --caddy, --homepage, --domain)
├── prometheus.yml                            # Scrape-Konfiguration (Server hier eintragen)
├── homepage/                                 # Statische Website
│   ├── index.html                            # Server-Übersicht (live via Prometheus, alle Metriken)
│   ├── servers.json                          # Anzeigenamen je server_name (Fallback wenn kein MOTD)
│   ├── *.html                                # Projektdokumentation (34 Seiten)
│   └── images/                              # Bilder
├── grafana/
│   ├── grafana.ini                           # Grafana-Konfiguration
│   ├── dashboards/
│   │   └── minecraft.json                   # Dashboard-Definition
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yaml              # Prometheus als Datenquelle
│       ├── dashboards/
│       │   └── dashboards.yaml              # Dashboard-Loader
│       └── alerting/
│           ├── contactpoints.yaml           # Discord-Webhook (hier URL eintragen)
│           ├── policies.yaml                # Alert-Routing
│           └── rules.yaml                   # Alert-Regeln
└── architecture.md                          # Detaillierte Architektur-Dokumentation
```

---

## Nützliche Befehle

```bash
# Stack starten (Core)
docker compose up -d

# Stack starten (Core + Caddy + Homepage)
docker compose -f docker-compose.yml -f compose.caddy.yml -f compose.homepage.yml up -d

# Stack stoppen
docker compose down

# Logs anzeigen
docker logs -f prometheus
docker logs -f grafana
docker logs -f caddy

# Prometheus neu laden (nach Änderung an prometheus.yml)
docker compose restart prometheus

# Caddy neu laden (nach Änderung am Caddyfile)
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```
