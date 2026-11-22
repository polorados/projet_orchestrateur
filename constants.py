import subprocess
from pathlib import Path

INTENT_FILE = Path("intent.json")
RTT_FILE = Path("data/rtt.json")
PROBE_PORT = 179
TIME_BETWEEN_PROBE = 5
BATCH_SIZE = 3

LAB = "sdwan"
TOPO = f"{LAB}.clab.yml"



def run(cmd, check=True):
    """Run a command and return its output."""
    print(">", " ".join(cmd))
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=True,
    )


def container(name):
    return f"clab-{LAB}-{name}"

def docker_exec(node, *args, check=True):
    return run(
        ["docker", "exec", container(node), *args],
        check=check,
    )

def ssh_exec(node, command, check=True):
    return run(
        ["ssh", node, command],
        check=check,
    )

def ping(host, destination, isSsh=False, source_ip=None):
    if not isSsh:
        result = docker_exec(
            host, "ping", "-c2", "-W2",
            destination, check=False
        )
        status = "OK" if result.returncode == 0 else "FAIL"
        print(f"[{status:4}] {host:7} -> {destination:14}")
    else:
        result = ssh_exec(
            host,
            f"ping -I {source_ip} -c2 -W2 {destination}"
        )


    return result.stdout