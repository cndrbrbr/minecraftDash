#!/usr/bin/env python3
"""
update-server-names.py
Liest MOTD aus server.properties der lokalen Docker-Container,
gleicht sie mit prometheus.yml ab und schreibt das Ergebnis in
homepage/servers.json.

Einmalig ausführen:
    python3 update-server-names.py

Cron (stündlich, als root):
    0 * * * * cd /root/mcDashProject/minecraftDash && python3 update-server-names.py
"""

import json
import re
import subprocess
import os
import sys

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
SERVERS_JSON    = os.path.join(SCRIPT_DIR, 'homepage', 'servers.json')
PROMETHEUS_YML  = os.path.join(SCRIPT_DIR, 'prometheus.yml')


def parse_targets(yml_path):
    """Gibt {server_name: port} zurück — nur Einträge mit einer Zahl als Port."""
    result = {}
    current_port = None
    with open(yml_path) as f:
        for line in f:
            m = re.search(r'targets.*:(\d+)', line)
            if m:
                current_port = int(m.group(1))
            m = re.search(r'server_name:\s*["\']?([^"\'#\s]+)["\']?', line)
            if m and current_port is not None:
                result[m.group(1)] = current_port
                current_port = None
    return result


def port_to_container(port):
    """Findet den Container-Namen, der Host-Port port gemappt hat."""
    try:
        out = subprocess.check_output(
            ['docker', 'ps', '--format', '{{.Names}}\t{{.Ports}}'],
            stderr=subprocess.DEVNULL
        ).decode()
        for line in out.splitlines():
            if '\t' not in line:
                continue
            name, ports = line.split('\t', 1)
            if f':{port}->' in ports:
                return name
    except Exception as e:
        print(f"  docker ps fehlgeschlagen: {e}", file=sys.stderr)
    return None


def read_motd(container):
    """Liest motd= aus server.properties im Container, entfernt Farbcodes."""
    try:
        out = subprocess.check_output(
            ['docker', 'exec', container, 'grep', '^motd=', '/server/server.properties'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        if out.startswith('motd='):
            motd = out[len('motd='):]
            motd = re.sub(r'§.', '', motd).strip()
            return motd if motd else None
    except Exception:
        pass
    return None


def main():
    # Bestehende servers.json laden
    existing = {}
    if os.path.exists(SERVERS_JSON):
        with open(SERVERS_JSON) as f:
            existing = json.load(f)

    targets = parse_targets(PROMETHEUS_YML)
    updated = dict(existing)
    changed = 0

    for server_name, port in sorted(targets.items()):
        container = port_to_container(port)
        if not container:
            print(f"  {server_name} (:{port}) — kein lokaler Container gefunden, übersprungen")
            continue
        motd = read_motd(container)
        if not motd:
            print(f"  {server_name} → {container}: kein MOTD gefunden")
            continue
        if updated.get(server_name) != motd:
            updated[server_name] = motd
            changed += 1
        print(f"  {server_name} → {container}: {motd}")

    if changed:
        with open(SERVERS_JSON, 'w', ensure_ascii=False) as f:
            json.dump(updated, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print(f"\nservers.json aktualisiert ({changed} Einträge geändert)")
    else:
        print("\nKeine Änderungen")


if __name__ == '__main__':
    main()
