#!/usr/bin/env python3
"""configure.py : applique les local-prefs décidées par decide.py sur les routeurs FRR.

Entrée (decide.py), fichier JSON ou stdin :
    {"edge-a": [{"neighbor": "10.0.1.1", "local_pref": 200}, ...], ...}

Pour chaque voisin, crée une route-map LP-<ip> (set local-preference) appliquée
en entrée, puis fait un soft reset BGP. Les commandes passent par
`ssh root@<ip mgmt> vtysh` : prévu pour tourner dans le conteneur controller,
l'IP de management de chaque routeur est lue dans intent.json.

Usage :
    python3 configure.py decisions.json
    python3 decide.py rtt.json | python3 configure.py
"""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

INTENT = Path(__file__).resolve().parent / "intent.json"

# Récupère l'ip d'un routeur donné si il est relié au controller. 
def mgmt_ip(ips: dict, router: str) -> str:
    """IP du routeur sur le lien vers le controller (ex. edge-a -> 1.1.1.1)."""
    return next(c.split("/")[0] for c, peer in ips[router].items() if peer == "controller")


def vtysh(router: str, ip: str, commands: list) -> None:
    remote = ["vtysh"]
    for c in commands:
        remote += ["-c", c]
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
           "-o", "ConnectTimeout=5", f"root@{ip}", shlex.join(remote)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[{router}] erreur : {res.stderr.strip()}", file=sys.stderr)
    else:
        print(f"[{router}] OK")


def configure(decisions: dict) -> None:
    intent = json.loads(INTENT.read_text())
    asn, ips = intent["AS"], intent["IP"]
    for router, neighbors in decisions.items():
        if router not in asn or router not in ips:
            print(f"[{router}] ignoré (absent de intent.json)", file=sys.stderr)
            continue
        cmds = ["configure terminal"]
        for n in neighbors:
            rm = f"LP-{n['neighbor']}"
            cmds += [
                f"route-map {rm} permit 10",
                f"set local-preference {n['local_pref']}",
                "exit",
            ]
        cmds += [f"router bgp {asn[router]}", "address-family ipv4 unicast"]
        cmds += [f"neighbor {n['neighbor']} route-map LP-{n['neighbor']} in"
                 for n in neighbors]
        cmds += ["end", "clear ip bgp * soft in"]
        vtysh(router, mgmt_ip(ips, router), cmds)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", nargs="?", help="fichier JSON de decide.py (défaut : stdin)")
    args = p.parse_args()

    if args.input:
        with open(args.input) as f:
            decisions = json.load(f)
    else:
        decisions = json.load(sys.stdin)
    configure(decisions)


if __name__ == "__main__":
    main()
