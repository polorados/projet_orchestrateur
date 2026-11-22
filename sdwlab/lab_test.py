import sys
import time

from config import BGP_CONFIGS, FRR_IMAGE, ROOT, ROUTERS, TOPOLOGY

from constants import TOPO, container, ping, run


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o644)


def write_topology():
    write_file(ROOT / TOPO, TOPOLOGY)


def write_daemons():
    result = run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "cat",
            FRR_IMAGE,
            "/etc/frr/daemons",
        ]
    )

    template = result.stdout.replace("bgpd=no", "bgpd=yes")

    for router in ROUTERS:
        write_file(
            ROOT / router / "daemons",
            template,
        )


def write_frr_configs():
    configs = BGP_CONFIGS.copy()

    for router, config in configs.items():
        write_file(ROOT / router / "frr.conf", config.strip() + "\n")


def docker_exec(node, *args, check=True):
    return run(
        ["docker", "exec", container(node), *args],
        check=check,
    )


def configure_hosts():
    hosts = {
        "host-a": ("192.168.1.2/24", "192.168.1.1"),
        "host-b": ("192.168.2.2/24", "192.168.2.1"),
        "host-c": ("192.168.3.2/24", "192.168.3.1"),
    }

    for host, (ip, gateway) in hosts.items():
        docker_exec(host, "ip", "link", "set", "eth1", "up")
        docker_exec(host, "ip", "addr", "add", ip, "dev", "eth1")
        docker_exec(
            host,
            "ip",
            "route",
            "add",
            "192.168.0.0/16",
            "via",
            gateway,
            "dev",
            "eth1",
        )
        docker_exec(
            host,
            "ip",
            "route",
            "add",
            "10.0.0.0/8",
            "via",
            gateway,
            "dev",
            "eth1",
        )
    controller_ip = {"eth1":"1.1.1.2/30", "eth2":"2.2.2.2/30", "eth3":"3.3.3.2/30"}
    # controller
    controller = "controller"
    for eth, ip in controller_ip.items():
        docker_exec(controller, "ip", "link", "set", eth, "up")
        docker_exec(controller, "ip", "addr", "add", ip, "dev", eth)
    docker_exec(
        controller,
        "ip",
        "route",
        "add",
        "10.0.0.0/8",
        "via",
        "1.1.1.1",
        "dev",
        "eth1",
    )



def setup_ssh():
    """Lance sshd sur les edges et y autorise la clé du controller."""
    pubkey = docker_exec("controller", "cat", "/root/.ssh/id_ed25519.pub").stdout.strip()

    for edge in ["edge-a", "edge-b", "edge-c"]:
        docker_exec(edge, "apk", "add", "--no-cache", "openssh-server")
        docker_exec(edge, "ssh-keygen", "-A")
        docker_exec(
            edge,
            "sh",
            "-c",
            "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
            f" && echo '{pubkey}' > /root/.ssh/authorized_keys"
            " && chmod 600 /root/.ssh/authorized_keys",
        )
        docker_exec(edge, "/usr/sbin/sshd")


def deploy():
    run(
        [
            "clab",
            "deploy",
            "--topo",
            TOPO,
            "--reconfigure",
        ]
    )

    for router in ROUTERS:
        docker_exec(
            router,
            "sysctl",
            "-qw",
            "net.ipv4.ip_forward=1",
            check=False,
        )


def destroy():
    run(
        [
            "clab",
            "destroy",
            "--topo",
            TOPO,
            "--cleanup",
        ]
    )


def show_bgp(router):
    result = docker_exec(
        router,
        "vtysh",
        "-c",
        "show bgp summary",
    )

    print(f"\n--- {router}")
    print(result.stdout)


def wait_for_bgp():
    print(">> Waiting for BGP convergence...")

    for _ in range(45):
        tests = [
            ("host-a", "192.168.2.2"),
            ("host-a", "192.168.3.2"),
            ("host-b", "192.168.3.2"),
        ]

        if all(
            docker_exec(
                host,
                "ping",
                "-c1",
                "-W1",
                destination,
                check=False,
            ).returncode == 0
            for host, destination in tests
        ):
            print(">> Converged.")
            return

        time.sleep(2)

    print(">> BGP did not fully converge.")


def run_tests():
    print("\n>> BGP sessions")

    for router in ROUTERS:
        show_bgp(router)

    print("\n>> Ping tests")

    tests = [
        ("host-a", "192.168.2.2", "host-b"),
        ("host-a", "192.168.3.2", "host-c"),
        ("host-b", "192.168.1.2", "host-a"),
        ("host-b", "192.168.3.2", "host-c"),
        ("host-c", "192.168.1.2", "host-a"),
        ("host-c", "192.168.2.2", "host-b"),
        ("host-a", "10.10.10.1", "isp1 loopback"),
        ("host-a", "10.10.10.2", "isp2 loopback"),
        ("host-a", "10.10.10.12", "edge-b loopback"),
        ("host-c", "10.10.10.11", "edge-a loopback"),
        ("host-a", "10.0.4.1", "isp2-edge-b link"),
        ("host-b", "10.0.0.2", "isp1-isp2 link"),
    ]

    for host, destination, label in tests:
        print(f"\n{label}")
        ping(host, destination)

    print("\n>> Path host-a -> host-c")

    result = docker_exec(
        "host-a",
        "traceroute",
        "-n",
        "-w1",
        "192.168.3.2",
        check=False,
    )

    print(result.stdout)

def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "up"

    if command == "up":
        write_topology()
        write_daemons()
        write_frr_configs()
        deploy()
        configure_hosts()
        setup_ssh()
        wait_for_bgp()
        run_tests()

    elif command == "test":
        run_tests()

    elif command == "down":
        destroy()

    else:
        print("Usage: python lab.py [up|test|down]")
        sys.exit(1)


if __name__ == "__main__":
    main()
