#!/usr/bin/env python3
"""
update-server-names.py
Liest die MOTD jedes Servers aus prometheus.yml und schreibt sie nach
homepage/servers.json (server_name -> MOTD). Das Dashboard zeigt die MOTD
als Titel und server_name / local_name als Untertitel.

- Lokale Container (Metrik-Port auf diesem Host gemappt): motd= aus
  server.properties im Container.
- Entfernte Server: Server-List-Ping auf connect_ip:connect_port.
Kann eine MOTD nicht gelesen werden (Server offline), bleibt der alte Wert.

Einmalig ausführen:
    python3 update-server-names.py

Cron (stündlich, als root):
    0 * * * * cd /root/mcDashProject/minecraftDash && python3 update-server-names.py
"""

import json
import os
import re
import socket
import struct
import subprocess
import sys

import yaml

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
SERVERS_JSON   = os.path.join(SCRIPT_DIR, 'homepage', 'servers.json')
PROMETHEUS_YML = os.path.join(SCRIPT_DIR, 'prometheus.yml')

PROPERTIES_PATHS = ['/server/data/cfg/server.properties', '/server/server.properties']


def parse_targets(yml_path):
    """Gibt [{server_name, target, connect_ip, connect_port}] zurück."""
    with open(yml_path) as f:
        cfg = yaml.safe_load(f)
    result = []
    for job in cfg.get('scrape_configs', []):
        for sc in job.get('static_configs', []):
            labels = sc.get('labels', {})
            if not labels.get('server_name'):
                continue
            for target in sc.get('targets', []):
                result.append({
                    'server_name':  labels['server_name'],
                    'target':       target,
                    'connect_ip':   labels.get('connect_ip') or target.rsplit(':', 1)[0],
                    'connect_port': int(labels.get('connect_port') or 25565),
                })
    return result


def docker_ports():
    try:
        out = subprocess.check_output(
            ['docker', 'ps', '--format', '{{.Names}}\t{{.Ports}}'],
            stderr=subprocess.DEVNULL
        ).decode()
    except Exception as e:
        print(f"  docker ps fehlgeschlagen: {e}", file=sys.stderr)
        return []
    return [line.split('\t', 1) for line in out.splitlines() if '\t' in line]


def local_ips():
    try:
        return set(subprocess.check_output(['hostname', '-I']).decode().split())
    except Exception:
        return set()


def clean(motd):
    motd = re.sub(r'§.', '', motd)
    motd = motd.replace('\\n', ' ').replace('\n', ' ')
    motd = re.sub(r'\s+', ' ', motd).strip()
    return motd or None


def read_motd_container(container):
    for path in PROPERTIES_PATHS:
        try:
            out = subprocess.check_output(
                ['docker', 'exec', container, 'grep', '^motd=', path],
                stderr=subprocess.DEVNULL
            ).decode()
        except Exception:
            continue
        line = out.splitlines()[0] if out else ''
        if line.startswith('motd='):
            # server.properties ist ISO-8859-1 mit \uXXXX-Escapes
            raw = line[len('motd='):].encode('latin-1', 'replace').decode('unicode_escape', 'replace')
            return clean(raw)
    return None


def _varint(n):
    out = b''
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _read_varint(sock):
    n = shift = 0
    while True:
        b = sock.recv(1)
        if not b:
            raise IOError('connection closed')
        n |= (b[0] & 0x7F) << shift
        if not b[0] & 0x80:
            return n
        shift += 7


def _text(component):
    if isinstance(component, str):
        return component
    if isinstance(component, list):
        return ''.join(_text(c) for c in component)
    if isinstance(component, dict):
        return _text(component.get('text', '')) + ''.join(_text(c) for c in component.get('extra', []))
    return ''


def read_motd_ping(host, port):
    """Server-List-Ping (Status-Protokoll)."""
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            s.settimeout(5)
            host_b = host.encode()
            hs = b'\x00' + _varint(767) + _varint(len(host_b)) + host_b + struct.pack('>H', port) + _varint(1)
            s.sendall(_varint(len(hs)) + hs + b'\x01\x00')
            _read_varint(s)                 # Paketlänge
            _read_varint(s)                 # Paket-ID
            length = _read_varint(s)
            data = b''
            while len(data) < length:
                chunk = s.recv(length - len(data))
                if not chunk:
                    break
                data += chunk
        status = json.loads(data.decode('utf-8', 'replace'))
        return clean(_text(status.get('description', '')))
    except Exception:
        return None


def main():
    existing = {}
    if os.path.exists(SERVERS_JSON):
        with open(SERVERS_JSON) as f:
            existing = json.load(f)

    ports = docker_ports()
    my_ips = local_ips()
    updated = dict(existing)
    changed = 0

    for t in parse_targets(PROMETHEUS_YML):
        name = t['server_name']
        host, mport = t['target'].rsplit(':', 1)
        container = None
        if host in my_ips or host in ('localhost', '127.0.0.1'):
            container = next((n for n, p in ports if f':{mport}->' in p), None)
        if container:
            motd, source = read_motd_container(container), container
        else:
            motd, source = read_motd_ping(t['connect_ip'], t['connect_port']), f"{t['connect_ip']}:{t['connect_port']}"
        if not motd:
            print(f"  {name} ({source}): keine MOTD, behalte {existing.get(name)!r}")
            continue
        if updated.get(name) != motd:
            updated[name] = motd
            changed += 1
        print(f"  {name} ({source}): {motd}")

    if changed:
        tmp = SERVERS_JSON + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(updated, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp, SERVERS_JSON)
        print(f"\nservers.json aktualisiert ({changed} Einträge geändert)")
    else:
        print("\nKeine Änderungen")


if __name__ == '__main__':
    main()
