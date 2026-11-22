#!/usr/bin/env python3
"""decide.py : transforme des mesures de RTT en local-prefs BGP.

Entrée (measure.py), fichier JSON :
    {"RTT_<time>": {"<ip source>": [rtt1, rtt2, ...], ...}}
    Le routeur de chaque IP source est retrouvé dans intent.json.

Sortie (configure.py) :
    {"edge-a": [{"neighbor": "10.0.1.1", "local_pref": 200},
            {"neighbor": "10.0.2.1", "local_pref": 100}],
    "edge-b": [...]}

Usage :
    python3 decide.py rtt.json            # résultat sur stdout
    python3 measure.py | python3 decide.py -o decisions.json
"""
import argparse
import json
import sys
from pathlib import Path

PREF_BEST = 200
PREF_OTHER = 100

INTENT = Path(__file__).resolve().parent / "intent.json"


def load_neighbors(path=INTENT) -> dict:
    """IP source (côté edge) -> (routeur, IP du voisin BGP en face).

    Ex : "10.0.1.2" -> ("edge-a", "10.0.1.1")
    """
    ips = json.loads(Path(path).read_text())["IP"]
    neighbors = {}
    for router, addrs in ips.items():
        for cidr, peer in addrs.items():
            src = cidr.split("/")[0]
            # IP du voisin : l'adresse du routeur 'peer' tournée vers 'router'
            peer_ip = next((c.split("/")[0] for c, r in ips.get(peer, {}).items()
                            if r == router), None)
            neighbors[src] = (router, peer_ip)
    return neighbors


NEIGHBORS = load_neighbors()


# def latest(measures: dict) -> dict:
#     """Retourne le bloc {ip: [rtt...]} de la mesure la plus récente."""
#     def t(key):
#         suffix = key.split("_", 1)[-1]
#         try:
#             return float(suffix)
#         except ValueError:
#             return suffix
#     return measures[max(measures, key=t)]
def latest(measures: dict) -> dict:
    """Retourne le bloc {ip: [rtt...]} de la mesure la plus récente."""
    return next(iter(measures.values()))


def mean_rtt(rtts: list) -> float:
    ok = [r for r in rtts if r is not None]
    return sum(ok) / len(ok) if ok else float("inf")


def decide(measures: dict) -> dict:
    groups = {}
    for ip, rtts in latest(measures).items():
        router, neighbor = NEIGHBORS.get(ip, ("unknown", ip))
        groups.setdefault(router, []).append((mean_rtt(rtts), neighbor))

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
    p.add_argument("input", nargs="?", help="fichier JSON de measure.py")
    p.add_argument("-o", "--output", help="fichier de sortie")
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
