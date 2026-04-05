# minecraftDash — Feature-Übersicht

Alle Features des Projekts mit Beschreibung und technischer Umsetzung.

---

## Inhaltsverzeichnis

- [Multi-Server-Monitoring mit Prometheus](#multi-server-monitoring-mit-prometheus)
- [Grafana-Dashboard](#grafana-dashboard)
- [Discord-Alerts](#discord-alerts)
- [Homepage mit Live-Server-Übersicht](#homepage-mit-live-server-übersicht)
- [Vollständige Metrik-Anzeige in Server-Karten](#vollständige-metrik-anzeige-in-server-karten)
- [Anzeigenamen aus MOTD](#anzeigenamen-aus-motd)
- [Automatische MOTD-Synchronisation](#automatische-motd-synchronisation)
- [Caddy Reverse Proxy](#caddy-reverse-proxy)
- [HTTPS mit automatischem TLS-Zertifikat](#https-mit-automatischem-tls-zertifikat)
- [Parametrisiertes Deployment](#parametrisiertes-deployment)
- [Setup-Script](#setup-script)
- [Statische Projektdokumentation](#statische-projektdokumentation)

---

## Multi-Server-Monitoring mit Prometheus

**Beschreibung:**
Mehrere Minecraft-Server werden zentral von einem einzigen Prometheus-Dienst überwacht. Jeder Server hat einen eindeutigen `server_name`-Label, über den Daten in Grafana und der Homepage gefiltert werden können. Neue Server können jederzeit durch einen Eintrag in `prometheus.yml` hinzugefügt werden, ohne den Stack neu zu bauen.

**Umsetzung:**
- Auf jedem Minecraft-Server läuft das Plugin **minecraft-prometheus-exporter**, das Metriken über HTTP auf Port `9940` bereitstellt.
- `prometheus.yml` definiert alle Scrape-Targets mit `server_name`-Labels:
  ```yaml
  static_configs:
    - targets: ["server-ip:9941"]
      labels:
        server_name: "mc1"
  ```
- Prometheus läuft als Docker-Container und scrapt alle Targets im 15-Sekunden-Intervall.
- Drei Szenarien werden unterstützt: externer Server (Internet), lokaler Container im selben Docker-Netzwerk, lokal gemappter Port.

---

## Grafana-Dashboard

**Beschreibung:**
Ein vorkonfiguriertes Dashboard **„Minecraft Dashboard"** wird beim Start automatisch bereitgestellt. Es zeigt Spielerzahlen, TPS und RAM-Verbrauch je Server als Zeitreihen. Ein Dropdown-Filter ermöglicht die Auswahl einzelner oder mehrerer Server.

**Umsetzung:**
- Dashboard-Definition in `grafana/dashboards/minecraft.json`.
- Automatisches Provisioning über `grafana/provisioning/dashboards/dashboards.yaml` — das Dashboard wird beim Start von Grafana geladen ohne manuelle Import-Schritte.
- Prometheus wird als Datenquelle über `grafana/provisioning/datasources/prometheus.yaml` vorkonfiguriert.
- Die Server-Variable im Dashboard nutzt `label_values(up{job="minecraft"}, server_name)` und erkennt neue Server automatisch.
- RAM-Heap-Berechnung: `mc_jvm_memory{type="allocated"} - ignoring(type) mc_jvm_memory{type="free"}` mit `ignoring(type)` um Label-Konflikte beim Binary-Join zu vermeiden.
- Grafana 12 deaktiviert file-basiertes Provisioning standardmäßig durch das Feature-Flag `kubernetesDashboards`. Dieses wird in `grafana/grafana.ini` explizit deaktiviert:
  ```ini
  [feature_toggles]
  kubernetesDashboards = false
  ```

---

## Discord-Alerts

**Beschreibung:**
Grafana sendet automatisch Benachrichtigungen an einen Discord-Channel wenn ein Server ausfällt oder die TPS dauerhaft niedrig sind.

**Umsetzung:**
- Alert-Regeln in `grafana/provisioning/alerting/rules.yaml`:
  - **Server Down**: `up{job="minecraft"} == 0` für 2 Minuten → critical
  - **TPS zu niedrig**: `mc_tps < 15` für 5 Minuten → warning
- Discord-Webhook-URL in `grafana/provisioning/alerting/contactpoints.yaml`.
- Routing über `grafana/provisioning/alerting/policies.yaml`.
- Alle Alerting-Konfigurationen werden beim Grafana-Start automatisch provisioniert.

---

## Homepage mit Live-Server-Übersicht

**Beschreibung:**
Eine statische Website zeigt eine Live-Übersicht aller Minecraft-Server mit Echtzeit-Daten aus Prometheus. Die Seite aktualisiert sich alle 15 Sekunden automatisch und zeigt einen Countdown bis zur nächsten Aktualisierung.

**Umsetzung:**
- `homepage/index.html` — reine Client-seitige Implementierung, kein Backend.
- JavaScript ruft die Prometheus HTTP API direkt über einen Caddy-Reverse-Proxy-Pfad `/api/prometheus/*` ab, da Browser kein direktes Cross-Origin-Fetch gegen Prometheus machen können.
- Alle Prometheus-Queries laufen parallel mit `Promise.all()` für minimale Ladezeit.
- Globale Zusammenfassung (Server online/offline, Spieler gesamt, Ø TPS, Entities gesamt) wird aus den Abfrageergebnissen berechnet.
- Caddy stellt die Homepage über `file_server` aus dem Verzeichnis `/srv` (gemountet aus `./homepage`) bereit.

---

## Vollständige Metrik-Anzeige in Server-Karten

**Beschreibung:**
Jede Server-Karte auf der Homepage zeigt alle verfügbaren Prometheus-Metriken an, aufgeteilt in thematische Bereiche.

**Umsetzung:**
- Folgende Metriken werden je Server abgefragt und angezeigt:

  | Bereich | Metriken |
  |---------|---------|
  | Header | Anzeigename, Version (`mc_server_info`), Online-Badge |
  | Spieler & Performance | Spieler (`mc_players_online_total`), TPS (`mc_tps`), RAM benutzt/max (`mc_jvm_memory`) |
  | Welt | Chunks (`mc_loaded_chunks_total`), Entities (`mc_entities_total`), Whitelist (`mc_whitelisted_players`) |
  | Tick-Timing | Median/Avg/Min/Max (`mc_tick_duration_*`) in ms |
  | JVM | Threads (`mc_jvm_threads_current`), GC-Events (`mc_jvm_gc_collection_seconds_count`), Weltgröße (`mc_world_size`) |

- TPS wird farbcodiert dargestellt: grün (≥ 18), gelb (≥ 15), rot (< 15).
- RAM wird in MB oder GB formatiert (`fmtBytes`), Tick-Zeiten in ms (`fmtNs` konvertiert aus Nanosekunden).
- Offline-Server zeigen `—` für alle Metriken statt falscher Nullwerte.

---

## Anzeigenamen aus MOTD

**Beschreibung:**
Server-Karten auf der Homepage zeigen den Anzeigenamen in einer definierten Priorität: zuerst die MOTD aus dem Plugin-Metric `mc_server_info`, dann manuell konfigurierte Namen aus `servers.json`, schließlich der interne `server_name`.

**Umsetzung:**
- Das Plugin exportiert (wenn `server_info: true` in der Plugin-Config) eine Metrik:
  ```
  mc_server_info{server_name="mc1", motd="A Minecraft Server", version="1.21"} 1
  ```
- `index.html` fragt `mc_server_info` ab und baut daraus ein `motdNames`-Mapping.
- Die Funktion `displayName(id)` gibt `motdNames[id] || serverNames[id] || id` zurück.
- Die Version aus `mc_server_info` wird als kleine Zusatzinfo neben dem `server_name` angezeigt.

---

## Automatische MOTD-Synchronisation

**Beschreibung:**
Da das Plugin `mc_server_info` in Version 3.1.2 nicht unterstützt, liest das Script `update-server-names.py` die MOTD direkt aus `server.properties` der lokalen Docker-Container und schreibt sie stündlich in `homepage/servers.json`.

**Umsetzung:**
- `update-server-names.py` parsed `prometheus.yml` mit Regex, um alle `server_name → port`-Zuordnungen zu ermitteln.
- Für jeden Port sucht `docker ps` den Container mit diesem gemappten Host-Port.
- `docker exec <container> grep '^motd=' /server/server.properties` liest den MOTD-Wert.
- Minecraft-Farbcodes (`§x`) werden per Regex entfernt.
- `homepage/servers.json` wird nur bei tatsächlichen Änderungen überschrieben.
- Remote-Server (kein lokaler Container für den Port gefunden) werden übersprungen — bestehende Einträge in `servers.json` bleiben erhalten.
- Cron-Eintrag für stündliche Ausführung:
  ```
  0 * * * * cd /root/mcDashProject/minecraftDash && python3 update-server-names.py
  ```

---

## Caddy Reverse Proxy

**Beschreibung:**
Caddy fungiert als Reverse Proxy vor Prometheus und als Dateiserver für die Homepage. Dadurch kann der Browser die Prometheus API über einen einheitlichen Origin aufrufen (kein CORS-Problem) und die Homepage wird über Standard-HTTP-Ports erreichbar.

**Umsetzung:**
- `Caddyfile` definiert zwei Funktionen:
  ```
  handle_path /api/prometheus/* {
      reverse_proxy prometheus:9090
  }
  ```
  Der Pfad `/api/prometheus/` wird durch `handle_path` automatisch gestripped bevor die Anfrage an Prometheus weitergeleitet wird.
- `file_server` serviert alle Dateien aus `/srv` (= `./homepage`).
- Caddy ist als opt-in Compose-Override in `compose.caddy.yml` definiert — der Core-Stack läuft auch ohne Caddy.
- Die Homepage wird über ein weiteres Compose-Override `compose.homepage.yml` als Read-only-Volume in Caddy eingehängt:
  ```yaml
  volumes:
    - ./homepage:/srv:ro
  ```

---

## HTTPS mit automatischem TLS-Zertifikat

**Beschreibung:**
Caddy holt automatisch ein TLS-Zertifikat von Let's Encrypt sobald eine Domain konfiguriert ist. Der gesamte HTTP-Traffic wird automatisch auf HTTPS umgeleitet.

**Umsetzung:**
- Das `setup.sh`-Script schreibt bei `--domain <domain>` ein `Caddyfile` mit dem Domain-Block statt `:80`:
  ```
  meckminecraft.de {
      root * /srv
      file_server
      handle_path /api/prometheus/* {
          reverse_proxy prometheus:9090
      }
  }
  ```
- Caddy erkennt den Domain-Block und startet den ACME-Challenge-Prozess automatisch.
- TLS-Zertifikat und -Konfiguration werden im Docker-Volume `caddy-data` persistent gespeichert und automatisch erneuert.
- Voraussetzung: DNS-A-Record der Domain muss auf die Server-IP zeigen, Port 80 und 443 müssen offen sein.

---

## Parametrisiertes Deployment

**Beschreibung:**
Der Stack besteht aus einem Core und optionalen Komponenten, die per Docker Compose Override-Dateien zugeschaltet werden. So läuft der Core auch ohne Caddy und Homepage, und die Konfiguration erfolgt ohne Änderungen an der Haupt-Compose-Datei.

**Umsetzung:**
- `docker-compose.yml` — Core: Prometheus + Grafana
- `compose.caddy.yml` — Opt-in: Caddy-Service mit Ports 80/443
- `compose.homepage.yml` — Opt-in: Homepage-Volume-Mount in Caddy (setzt Caddy voraus)
- Docker Compose mergt die Dateien zur Laufzeit:
  ```bash
  docker compose -f docker-compose.yml -f compose.caddy.yml -f compose.homepage.yml up -d
  ```
- Volumes für Caddy (`caddy-data`, `caddy-config`) sind in `compose.caddy.yml` definiert, nicht im Core — sie existieren nur wenn Caddy aktiv ist.

---

## Setup-Script

**Beschreibung:**
`setup.sh` abstrahiert die Docker Compose Override-Logik hinter einfachen Parametern, schreibt das `Caddyfile` automatisch und gibt nach dem Start alle Dienst-URLs aus.

**Umsetzung:**
- Parameter: `--caddy`, `--homepage`, `--domain <domain>`, `--down`, `--dry-run`
- `--domain` setzt implizit `--caddy` und `--homepage` und schreibt ein HTTPS-`Caddyfile`.
- Vor dem Start werden bestehende Container (`caddy`, `prometheus`, `grafana`) mit `docker rm -f` entfernt, um den Docker-Netzwerk-Timing-Bug zu umgehen (stale Container halten Referenzen auf alte Netzwerk-IDs).
- Das Script baut den `docker compose`-Befehl dynamisch aus einem Array auf und zeigt ihn vor der Ausführung an.

---

## Statische Projektdokumentation

**Beschreibung:**
Die Homepage enthält neben dem Live-Dashboard eine vollständige Projektdokumentation in Form von 34 statischen HTML-Seiten, die aus der ursprünglichen WordPress-Seite des Projekts wiederhergestellt wurden.

**Umsetzung:**
- Inhalte aus der WordPress-Datenbank `wp_mine` wurden über eine temporäre MariaDB 10.5-Instanz mit `--innodb-force-recovery=1` extrahiert.
- Ein Python-Script generierte aus den Datenbank-Inhalten statische HTML-Dateien mit einheitlichem Dark-Theme-Layout und Sidebar-Navigation.
- Bild-URLs wurden von absoluten WordPress-Upload-Pfaden auf relative `images/`-Verzeichnis-Referenzen umgeschrieben.
- 42 Bilder aus dem originalen WordPress-Upload-Verzeichnis wurden in `homepage/images/` kopiert.
- Alle Seiten teilen dasselbe CSS (Dark-Theme, Sidebar, Content-Bereich) und sind per `<nav>`-Sidebar miteinander verlinkt.
