import ipaddress
import json
import time
import re

from constants import *
from scapy.all import sr1
from scapy.layers.inet import IP, TCP

with INTENT_FILE.open() as file:
    data = json.load(file)

ping_match = re.compile(
    r"round-trip min/avg/max = ([\d.]+)/([\d.]+)/([\d.]+) ms"
).search

def get_router_ips() -> list[ipaddress.IPv4Address]:
    # get all ips from the intent.json
    ips = set()

    for as_data in data.values():
        for router, interfaces in as_data.items():
            if router == "controller" : continue

            for interface in interfaces:
                ips.add(ipaddress.ip_interface(interface).ip)

    return list(ips)

def send_rtt_probe(ip:ipaddress.IPv4Address, n:int) -> dict[str, list[float]]:
    # sends a TCP probe and measures its RTT
    results = []

    for _ in range(n):
        packet = IP(dst=str(ip)) / TCP(
            dport=PROBE_PORT,
            flags="S"
        )

        start = time.perf_counter()

        _ = sr1(packet, timeout=2, verbose=False)

        rtt = (time.perf_counter() - start) * 1000
        results.append(round(rtt, 3))

    return {str(ip): results}

def get_source_ip(source:str, destimation_ip:str):
    ips = data["IP"]
    destination_name = ips[source][destimation_ip]
    source_ip = ""
    for key, value in ips[destimation_ip].items():
        if value == destination_name:
            source_ip = key
    return source_ip


def send_full_rtt_probe(batch_size: int, isSsh:bool=False):
    name = f"RTT_{time.time()}"
    measurements = {name: {}}

    ips = data["IP"]

    for source, destinations in ips.items():
        if not source.startswith("edge"): continue

        for destination_ip in destinations:
            # Remove CIDR notation
            destination_ip = destination_ip.split("/")[0]
            measurements[name].setdefault(destination_ip, [])

            for _ in range(batch_size // 2):
                output = ping(source, destination_ip, isSsh, get_source_ip(source, destination_ip))
                match = ping_match(output)

                if match:
                    min_rtt, _, max_rtt = map(float, match.groups())
                    measurements[name][destination_ip].extend(
                        [min_rtt, max_rtt]
                    )

    return measurements

    
