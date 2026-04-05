# 🧱 Minecraft Monitoring Architektur (Prometheus + Grafana)

## Übersicht

Dieses Setup überwacht mehrere Minecraft-Server (Proxy + Backends) mit:

- Prometheus (Datensammlung)
- Grafana (Visualisierung + Alerts)
- Exporter auf jedem Server
- Discord (Alerts)

---

## 🌐 Architekturdiagramm

```
                                   INTERNET
                                      |
                     +-----------------------------------+
                     |  Minecraft Clients / Browser      |
                     +----------------+------------------+
                                      |
                +---------------------+----------------------+
                |                                            |
                v                                            v

   +----------------------------------------------------------------------------------+
   |                               PROXY SERVER                                       |
   |                    (BungeeCord / Velocity / Waterfall)                           |
   |----------------------------------------------------------------------------------|
   | Tools:                                                                           |
   |   - Proxy Server                                                                 |
   |   - Prometheus Exporter                                                          |
   |                                                                                  |
   | Files:                                                                           |
   |   /opt/proxy/                                                                    |
   |     proxy.jar                                                                    |
   |     config.yml                                                                   |
   |     plugins/velocity-prometheus-exporter.jar                                     |
   |                                                                                  |
   | Metrics Endpoint:                                                                |
   |   http://proxy:9985/metrics                                                      |
   +-----------------------------------+----------------------------------------------+
                                       |
                                       v

             +-------------------------+--------------------------+
             |                                                    |
             v                                                    v

   +----------------------------------------+        +----------------------------------------+
   | BACKEND SERVER (Survival)              |        | BACKEND SERVER (Lobby)                 |
   |----------------------------------------|        |----------------------------------------|
   | Tools:                                 |        | Tools:                                 |
   |   - Paper / Spigot                     |        |   - Paper / Spigot                     |
   |   - Prometheus Exporter                |        |   - Prometheus Exporter                |
   |   - spark (optional)                   |        |   - spark (optional)                   |
   |                                        |        |                                        |
   | Files:                                 |        | Files:                                 |
   |   /opt/mc-survival/                    |        |   /opt/mc-lobby/                       |
   |     server.jar                         |        |     server.jar                         |
   |     server.properties                  |        |     server.properties                  |
   |     plugins/PrometheusExporter.jar     |        |     plugins/PrometheusExporter.jar     |
   |     plugins/spark.jar                  |        |     plugins/spark.jar                  |
   |     plugins/PrometheusExporter/config.yml                                            |
   |                                        |        |                                        |
   | Metrics Endpoint:                      |        | Metrics Endpoint:                      |
   |   http://backend:9940/metrics          |        |   http://backend:9940/metrics          |
   +-------------------+--------------------+        +-------------------+--------------------+
                           ^                                                     ^
                           |                                                     |
                           +------------------------+----------------------------+
                                                    |
                                                    v

   +----------------------------------------------------------------------------------+
   |                         MONITORING SERVER (Docker)                                |
   |----------------------------------------------------------------------------------|
   | Tools:                                                                           |
   |   - Prometheus                                                                   |
   |   - Grafana                                                                      |
   |                                                                                  |
   | Files:                                                                           |
   |   /opt/monitoring/                                                               |
   |     docker-compose.yml                                                           |
   |     prometheus.yml                                                               |
   |     grafana/dashboards/                                                          |
   |       minecraft-dashboard.json                                                   |
   |       bungeecord-dashboard.json                                                  |
   |                                                                                  |
   | Ports:                                                                           |
   |   9090 = Prometheus                                                             |
   |   3000 = Grafana                                                                |
   +-----------------------------------+----------------------------------------------+
                                       |
                                       v

                           +----------------------------------+
                           |          DISCORD                  |
                           |   Webhook Alerts                  |
                           +----------------------------------+
```

---

## 🔄 Datenfluss

```
Players
   |
   v
Proxy (Bungee/Velocity)
   |
   +--> Backend Server (Survival)
   |
   +--> Backend Server (Lobby)

Prometheus
   |
   +--> scrapt Proxy (Port 9985)
   |
   +--> scrapt Backend (Port 9940)

Grafana
   |
   +--> liest Prometheus
   +--> zeigt Dashboards
   +--> sendet Alerts → Discord
```

---

## 📂 Verzeichnisstruktur

### 🖥 Monitoring Server

```
/opt/monitoring/
├── docker-compose.yml
├── prometheus.yml
└── grafana/
    └── dashboards/
        ├── minecraft-grafana-dashboard.json
        └── bungeecord-dashboard.json
```

---

### 🌐 Proxy Server

```
/opt/proxy/
├── proxy.jar
├── config.yml
└── plugins/
    └── velocity-prometheus-exporter.jar
```

---

### 🎮 Backend Server

```
/opt/mc-survival/
├── server.jar
├── server.properties
├── paper.yml
└── plugins/
    ├── PrometheusExporter.jar
    ├── spark.jar
    └── PrometheusExporter/
        └── config.yml
```

---

## ⚙️ Prometheus Konfiguration

```yaml
global:
  scrape_interval: 10s

scrape_configs:
  - job_name: "bungeecord"
    static_configs:
      - targets: ["proxy1.example.net:9985"]
        labels:
          proxy_name: "proxy1"

  - job_name: "minecraft"
    static_configs:
      - targets: ["mc-survival.example.net:9940"]
        labels:
          server_name: "survival"

      - targets: ["mc-lobby.example.net:9940"]
        labels:
          server_name: "lobby"
```

---

## 🐳 Docker Setup

```yaml
version: "3.8"

services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - ./grafana/dashboards:/var/lib/grafana/dashboards
```

---

## 🔔 Alerts (Beispiele)

```promql
# Server down
up{job="minecraft"} == 0

# TPS zu niedrig
avg_over_time(mc_tps[2m]) < 18

# MSPT kritisch
avg_over_time(mc_tick_duration_average[2m]) > 50000000

# Proxy down
up{job="bungeecord"} == 0
```

---

## 💡 Komponentenübersicht

| Komponente | Aufgabe |
|-----------|--------|
| Prometheus | sammelt Metriken |
| Grafana | Dashboards + Alerts |
| Exporter | liefert Minecraft-Daten |
| Proxy | verteilt Spieler |
| Backend | führt Minecraft aus |
| Discord | empfängt Alerts |

---

## 🚀 Empfehlung

**Einfach:**
- Uptime Kuma + Prometheus

**Pro-Level:**
- Prometheus + Grafana + Exporter + Discord Alerts
