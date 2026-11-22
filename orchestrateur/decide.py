#!/usr/bin/env python3
"""decide.py : transforme des mesures de RTT en local-prefs BGP.

Entrée (measure.py), fichier JSON ou stdin :
    {"RTT_<time>": {"<ip>": [rtt1, rtt2, ...], ...}, ...}
    (un RTT à null = ping perdu)

Sortie (configure.py), sur stdout ou dans un fichier :
    {"edge-a": [{"neighbor": "10.0.1.1", "local_pref": 200}, ...], ...}

Pour chaque routeur, le voisin dont le RTT moyen (dernière mesure) est le
plus faible reçoit PREF_BEST, les autres PREF_OTHER.

Usage :
    python3 decide.py rtt.json            # résultat sur stdout
    python3 measure.py | python3 decide.py -o decisions.json
"""
import argparse
import json
import sys

PREF_BEST = 200
PREF_OTHER = 100

# IP du voisin BGP (côté ISP) -> routeur sur lequel appliquer la local-pref
NEIGHBORS = {
    "10.0.1.1": "edge-a", "10.0.2.1": "edge-a",
    "10.0.3.1": "edge-b", "10.0.4.1": "edge-b",
    "10.0.5.1": "edge-c", "10.0.6.1": "edge-c",
}


def latest(measures: dict) -> dict:
    """Retourne le bloc {ip: [rtt...]} de la mesure la plus récente."""
    def t(key):
        suffix = key.split("_", 1)[-1]
        try:
            return float(suffix)
        except ValueError:
            return suffix
    return measures[max(measures, key=t)]


def mean_rtt(rtts: list) -> float:
    ok = [r for r in rtts if r is not None]
    return sum(ok) / len(ok) if ok else float("inf")


def decide(measures: dict) -> dict:
    groups = {}
    for ip, rtts in latest(measures).items():
        router = NEIGHBORS.get(ip, "unknown")
        groups.setdefault(router, []).append((mean_rtt(rtts), ip))

    decisions = {}
    for router, links in groups.items():
        best_ip = min(links)[1]
        decisions[router] = [
            {"neighbor": ip, "local_pref": PREF_BEST if ip == best_ip else PREF_OTHER}
            for _, ip in sorted(links, key=lambda x: x[1])
        ]
    return decisions


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", nargs="?", help="fichier JSON de measure.py (défaut : stdin)")
    p.add_argument("-o", "--output", help="fichier de sortie (défaut : stdout)")
    args = p.parse_args()

    if args.input:
        with open(args.input) as f:
            measures = json.load(f)
    else:
        measures = json.load(sys.stdin)

    out = json.dumps(decide(measures), indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(out + "\n")
    else:
        print(out)


if __name__ == "__main__":
    main()
