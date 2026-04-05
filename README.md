# minecraftDash

Zentrale Überwachung mehrerer Minecraft-Server mit Prometheus, Grafana und Discord-Alerts.

## Inhalt

- [Architektur](#architektur)
- [Voraussetzungen](#voraussetzungen)
- [Schnellstart (lokal)](#schnellstart-lokal)
- [Minecraft-Server einrichten](#minecraft-server-einrichten)
- [Weiteren Server hinzufügen](#weiteren-server-hinzufügen)
- [Discord-Alerts einrichten](#discord-alerts-einrichten)
- [Grafana-Dashboard](#grafana-dashboard)
- [Verzeichnisstruktur](#verzeichnisstruktur)

---

## Architektur

```
Minecraft Server 1  ──┐
  (Plugin :9940)      │
                      ▼
Minecraft Server 2  ──▶  Prometheus  ──▶  Grafana  ──▶  Discord
  (Plugin :9940)      │   (:9090)          (:3000)       (Alerts)
                      │
Minecraft Server N  ──┘
  (Plugin :9940)
```

Auf jedem Minecraft-Server läuft das Plugin **minecraft-prometheus-exporter**, das Metriken (Spieleranzahl, TPS, RAM) über HTTP bereitstellt. Prometheus sammelt diese Daten zentral ein. Grafana visualisiert sie und sendet Alerts an Discord.

---

## Voraussetzungen

- Docker + Docker Compose
- Netzwerkzugriff vom Monitoring-Server zu Port `9940` aller Minecraft-Server

---

## Firewall (iptables)

Docker-published Ports umgehen die `INPUT`-Chain. Regeln für Docker-Container gehören in die `DOCKER-USER`-Chain.

```bash
# Platzhalter ersetzen:
ADMIN_IP="<IP_DES_ADMINS>"   # z. B. 1.2.3.4

# ── Grafana (container-intern: 3000) ─────────────────────────
# Nur der Admin darf auf das Dashboard zugreifen.
iptables -I DOCKER-USER -p tcp --dport 3000 -s "$ADMIN_IP" -j ACCEPT
iptables -I DOCKER-USER -p tcp --dport 3000 -j DROP

# ── Prometheus (container-intern: 9090) ──────────────────────
# Nur lokal / Admin erreichbar — nicht öffentlich.
iptables -I DOCKER-USER -p tcp --dport 9090 -s 127.0.0.1   -j ACCEPT
iptables -I DOCKER-USER -p tcp --dport 9090 -s "$ADMIN_IP" -j ACCEPT
iptables -I DOCKER-USER -p tcp --dport 9090 -j DROP

# ── Test-Minecraft (container-intern: 25565, Host-Port 25570) ─
# Nur lokal erreichbar — nicht öffentlich.
iptables -I DOCKER-USER -p tcp --dport 25565 -s 127.0.0.1 -j ACCEPT
iptables -I DOCKER-USER -p tcp --dport 25565 -j DROP

# ── Ausgehend zu Minecraft-Servern (Port 9940) ────────────────
# Prometheus muss die Exporter-Endpunkte der MC-Server erreichen.
# Ausgehender Traffic ist standardmäßig erlaubt (OUTPUT ACCEPT).
# Nur nötig, falls die OUTPUT-Chain eingeschränkt ist:
# iptables -A OUTPUT -p tcp --dport 9940 -j ACCEPT
```

> **Regeln dauerhaft speichern** (Debian/Ubuntu):
> ```bash
> apt install iptables-persistent
> netfilter-persistent save
> ```

> **Regeln prüfen:**
> ```bash
> iptables -L DOCKER-USER -n --line-numbers
> ```

> **Einzelne Regel entfernen** (Zeilennummer aus obigem Befehl):
> ```bash
> iptables -D DOCKER-USER <nummer>
> ```

---

## Schnellstart (lokal)

```bash
git clone https://github.com/cndrbrbr/minecraftDash.git
cd minecraftDash

# Discord-Webhook eintragen (optional, für Alerts)
# grafana/provisioning/alerting/contactpoints.yaml bearbeiten

docker compose up -d
```

| Dienst     | URL                      | Zugangsdaten  |
|------------|--------------------------|---------------|
| Grafana    | http://localhost:3000    | admin / admin |
| Prometheus | http://localhost:9090    | —             |
| Minecraft  | localhost:25570          | Offline-Modus |

> Der Minecraft-Server startet beim ersten Start etwas langsamer, da Spigot heruntergeladen wird.
> Status prüfen: `docker logs -f minecraft`

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
Standardmäßig bindet es auf `localhost` — für externe Zugriffe auf `0.0.0.0` ändern:

```yaml
host: 0.0.0.0
port: 9940
```

Server neu laden: `/reload` oder Neustart.

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

Bevor ein Server in Prometheus eingetragen wird, muss dort das Plugin laufen und von außen erreichbar sein (siehe [Minecraft-Server einrichten](#minecraft-server-einrichten)).

Status prüfen:
```bash
curl http://<server-ip>:9940/metrics
```
Gibt die Seite Metriken zurück, ist der Server bereit.

---

### Szenario 1 — Externer Server (Internet)

Der Server läuft irgendwo im Internet und ist über eine öffentliche IP oder Domain erreichbar.

**`prometheus.yml` ergänzen:**

```yaml
scrape_configs:
  - job_name: "minecraft"
    static_configs:
      - targets: ["minecraft:9940"]
        labels:
          server_name: "local-test"

      # Neuer externer Server:
      - targets: ["mein-server.example.com:9940"]
        labels:
          server_name: "survival"
```

**Firewall auf dem Minecraft-Server:**
```bash
# Nur die IP des Monitoring-Servers erlauben
ufw allow from <monitoring-ip> to any port 9940
```

---

### Szenario 2 — Lokaler Server im selben Docker-Netzwerk

Der Server läuft als Docker-Container auf demselben Host (z. B. aus [minecraftHostingServer](https://github.com/cndrbrbr/minecraftHostingServer)).

Da der Prometheus-Container standardmäßig nur im `mcdash`-Netzwerk ist, muss er einmalig mit dem Netzwerk des anderen Stacks verbunden werden:

```bash
# Einmalig ausführen — verbindet Prometheus mit dem anderen Docker-Netzwerk
docker network connect <netzwerk-name> prometheus

# Netzwerkname herausfinden:
docker network ls
```

Beispiel für minecraftHostingServer:
```bash
docker network connect minecrafthostingserver_default prometheus
```

**`prometheus.yml` ergänzen** — Container-Name als Hostname:

```yaml
      - targets: ["mc1:9940"]
        labels:
          server_name: "mc1"

      - targets: ["mc2:9940"]
        labels:
          server_name: "mc2"
```

> Die `docker network connect`-Verbindung geht beim Neustart des Prometheus-Containers verloren.
> Um sie dauerhaft zu machen, das Netzwerk in `docker-compose.yml` unter `prometheus` eintragen:
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

---

### Szenario 3 — Lokaler Server, Port nach außen gemappt

Port 9940 des Containers ist auf einen Host-Port gemappt (z. B. `9941:9940`).
Prometheus erreicht ihn dann über `host.docker.internal` oder die Host-IP:

```yaml
      - targets: ["host.docker.internal:9941"]
        labels:
          server_name: "mc1"
```

---

### Prometheus neu laden

Nach jeder Änderung an `prometheus.yml`:

```bash
./restart-prometheus.sh
```

oder manuell:

```bash
docker compose restart prometheus
```

Das Grafana-Dashboard erkennt neue Server automatisch über die `server_name`-Variable.

---

## Discord-Alerts einrichten

### 1. Discord-Webhook erstellen

In Discord: **Servereinstellungen → Integrationen → Webhooks → Neuen Webhook erstellen**
Webhook-URL kopieren.

### 2. URL eintragen

Datei `grafana/provisioning/alerting/contactpoints.yaml` öffnen und URL eintragen:

```yaml
settings:
  url: "https://discord.com/api/webhooks/DEINE_WEBHOOK_URL"
```

### 3. Grafana neu starten

```bash
docker compose restart grafana
```

### Vorkonfigurierte Alerts

| Alert          | Bedingung              | Schwere  |
|----------------|------------------------|----------|
| Server Down    | Server nicht erreichbar für 2 min | critical |
| TPS zu niedrig | TPS < 15 für 5 min     | warning  |

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

## Verzeichnisstruktur

```
minecraftDash/
├── docker-compose.yml                        # Stack-Definition
├── prometheus.yml                            # Scrape-Konfiguration (Server hier eintragen)
├── plugins/
│   └── minecraft-prometheus-exporter.jar     # Spigot-Plugin
├── grafana/
│   ├── dashboards/
│   │   └── minecraft.json                    # Dashboard-Definition
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yaml               # Prometheus als Datenquelle
│       ├── dashboards/
│       │   └── dashboards.yaml               # Dashboard-Loader
│       └── alerting/
│           ├── contactpoints.yaml            # Discord-Webhook (hier URL eintragen)
│           ├── policies.yaml                 # Alert-Routing
│           └── rules.yaml                    # Alert-Regeln
└── architecture.md                           # Detaillierte Architektur-Dokumentation
```

---

## Nützliche Befehle

```bash
# Stack starten
docker compose up -d

# Stack stoppen
docker compose down

# Logs anzeigen
docker logs -f minecraft
docker logs -f prometheus
docker logs -f grafana

# Minecraft-Konsole (RCON)
docker exec -it minecraft rcon-cli --host localhost --port 25575 --password testpass123

# Prometheus neu laden (nach Änderung an prometheus.yml)
docker compose restart prometheus

# Metriken direkt prüfen
curl http://localhost:9940/metrics
```
