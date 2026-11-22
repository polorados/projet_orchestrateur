from scapy.layers.inet import IP, ICMP, TCP, UDP
from scapy.all import send, sr, sr1, sniff
import json
from pathlib import Path
import ipaddress
import time

INTENT_FILE = Path("intent.json")
RTT_FILE = Path("data/rtt.json")
PROBE_PORT = 179
TIME_BETWEEN_PROBE = 5
BATCH_SIZE = 3


with INTENT_FILE.open() as file:
    data = json.load(file)

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

def send_full_rtt_probe(batch_size:int):
    # sends a batch of batch_size RTT probe and save the output in data/rtt.json
    """json 
    RTT_{time}:{
        ip1:[RTT_1, RTT_2, RTT_3, ...]
        ip2:[RTT_1, RTT_2, RTT_3, ...]
        ...
    },
    """
    name = f"RTT_{time.time()}"
    measurements = {name:{}}

    for ip in get_router_ips():
        measurements.get(name, {}).update(send_rtt_probe(ip, batch_size))

    with RTT_FILE.open("w") as file:
        json.dump(measurements, file, indent=4)


while True:
    time.sleep(TIME_BETWEEN_PROBE)
    send_full_rtt_probe(BATCH_SIZE)
