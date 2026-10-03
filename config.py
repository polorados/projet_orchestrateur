LAB = "sdwan"
TOPO = f"{LAB}.clab.yml"
FRR_IMAGE = "quay.io/frrouting/frr:10.0.1"
HOST_IMAGE = "alpine:latest"

ROUTERS = ["isp1", "isp2", "edge-a", "edge-b", "edge-c"]
HOSTS = ["host-a", "host-b", "host-c"]

ROOT = Path(__file__).resolve().parent

TOPOLOGY = f"""\
name: {LAB}

topology:
  nodes:
    isp1:
      kind: linux
      image: {FRR_IMAGE}
      binds:
        - isp1/daemons:/etc/frr/daemons
        - isp1/frr.conf:/etc/frr/frr.conf

    isp2:
      kind: linux
      image: {FRR_IMAGE}
      binds:
        - isp2/daemons:/etc/frr/daemons
        - isp2/frr.conf:/etc/frr/frr.conf

    edge-a:
      kind: linux
      image: {FRR_IMAGE}
      binds:
        - edge-a/daemons:/etc/frr/daemons
        - edge-a/frr.conf:/etc/frr/frr.conf

    edge-b:
      kind: linux
      image: {FRR_IMAGE}
      binds:
        - edge-b/daemons:/etc/frr/daemons
        - edge-b/frr.conf:/etc/frr/frr.conf

    edge-c:
      kind: linux
      image: {FRR_IMAGE}
      binds:
        - edge-c/daemons:/etc/frr/daemons
        - edge-c/frr.conf:/etc/frr/frr.conf

    host-a:
      kind: linux
      image: {HOST_IMAGE}

    host-b:
      kind: linux
      image: {HOST_IMAGE}

    host-c:
      kind: linux
      image: {HOST_IMAGE}

  links:
    - endpoints: ["edge-a:eth1", "isp1:eth1"]
    - endpoints: ["edge-a:eth2", "isp2:eth1"]
    - endpoints: ["edge-b:eth1", "isp1:eth2"]
    - endpoints: ["edge-b:eth2", "isp2:eth2"]
    - endpoints: ["host-a:eth1", "edge-a:eth3"]
    - endpoints: ["host-b:eth1", "edge-b:eth3"]
    - endpoints: ["isp1:eth3", "isp2:eth3"]
    - endpoints: ["edge-c:eth1", "isp1:eth4"]
    - endpoints: ["edge-c:eth2", "isp2:eth4"]
    - endpoints: ["host-c:eth1", "edge-c:eth3"]
"""

BGP_CONFIGS = {
        "isp1": """
frr defaults traditional
hostname isp1
no ipv6 forwarding
!
interface eth1
 ip address 10.0.1.1/30
!
interface eth2
 ip address 10.0.3.1/30
!
interface eth3
 ip address 10.0.0.1/30
!
interface eth4
 ip address 10.0.5.1/30
!
interface lo
 ip address 10.10.10.1/32
!
router bgp 65001
 bgp router-id 10.10.10.1
 no bgp ebgp-requires-policy
 neighbor 10.0.1.2 remote-as 65101
 neighbor 10.0.3.2 remote-as 65102
 neighbor 10.0.5.2 remote-as 65103
 neighbor 10.0.0.2 remote-as 65002
 !
 address-family ipv4 unicast
  network 10.10.10.1/32
  network 10.0.0.0/30
  network 10.0.1.0/30
  network 10.0.3.0/30
  network 10.0.5.0/30
 exit-address-family
!
line vty
!
""",

        "isp2": """
frr defaults traditional
hostname isp2
no ipv6 forwarding
!
interface eth1
 ip address 10.0.2.1/30
!
interface eth2
 ip address 10.0.4.1/30
!
interface eth3
 ip address 10.0.0.2/30
!
interface eth4
 ip address 10.0.6.1/30
!
interface lo
 ip address 10.10.10.2/32
!
router bgp 65002
 bgp router-id 10.10.10.2
 no bgp ebgp-requires-policy
 neighbor 10.0.2.2 remote-as 65101
 neighbor 10.0.4.2 remote-as 65102
 neighbor 10.0.6.2 remote-as 65103
 neighbor 10.0.0.1 remote-as 65001
 !
 address-family ipv4 unicast
  network 10.10.10.2/32
  network 10.0.0.0/30
  network 10.0.2.0/30
  network 10.0.4.0/30
  network 10.0.6.0/30
 exit-address-family
!
line vty
!
""",

        "edge-a": """
frr defaults traditional
hostname edge-a
no ipv6 forwarding
!
interface eth1
 ip address 10.0.1.2/30
!
interface eth2
 ip address 10.0.2.2/30
!
interface eth3
 ip address 192.168.1.1/24
!
interface lo
 ip address 10.10.10.11/32
!
bgp as-path access-list LOCAL-ONLY permit ^$
!
route-map EXPORT-LOCAL permit 10
 match as-path LOCAL-ONLY
!
router bgp 65101
 bgp router-id 10.10.10.11
 no bgp ebgp-requires-policy
 neighbor 10.0.1.1 remote-as 65001
 neighbor 10.0.2.1 remote-as 65002
 !
 address-family ipv4 unicast
  network 10.10.10.11/32
  network 10.0.1.0/30
  network 10.0.2.0/30
  network 192.168.1.0/24
  neighbor 10.0.1.1 route-map EXPORT-LOCAL out
  neighbor 10.0.2.1 route-map EXPORT-LOCAL out
 exit-address-family
!
line vty
!
""",

        "edge-b": """
frr defaults traditional
hostname edge-b
no ipv6 forwarding
!
interface eth1
 ip address 10.0.3.2/30
!
interface eth2
 ip address 10.0.4.2/30
!
interface eth3
 ip address 192.168.2.1/24
!
interface lo
 ip address 10.10.10.12/32
!
bgp as-path access-list LOCAL-ONLY permit ^$
!
route-map EXPORT-LOCAL permit 10
 match as-path LOCAL-ONLY
!
router bgp 65102
 bgp router-id 10.10.10.12
 no bgp ebgp-requires-policy
 neighbor 10.0.3.1 remote-as 65001
 neighbor 10.0.4.1 remote-as 65002
 !
 address-family ipv4 unicast
  network 10.10.10.12/32
  network 10.0.3.0/30
  network 10.0.4.0/30
  network 192.168.2.0/24
  neighbor 10.0.3.1 route-map EXPORT-LOCAL out
  neighbor 10.0.4.1 route-map EXPORT-LOCAL out
 exit-address-family
!
line vty
!
""",

        "edge-c": """
frr defaults traditional
hostname edge-c
no ipv6 forwarding
!
interface eth1
 ip address 10.0.5.2/30
!
interface eth2
 ip address 10.0.6.2/30
!
interface eth3
 ip address 192.168.3.1/24
!
interface lo
 ip address 10.10.10.13/32
!
bgp as-path access-list LOCAL-ONLY permit ^$
!
route-map EXPORT-LOCAL permit 10
 match as-path LOCAL-ONLY
!
router bgp 65103
 bgp router-id 10.10.10.13
 no bgp ebgp-requires-policy
 neighbor 10.0.5.1 remote-as 65001
 neighbor 10.0.6.1 remote-as 65002
 !
 address-family ipv4 unicast
  network 10.10.10.13/32
  network 10.0.5.0/30
  network 10.0.6.0/30
  network 192.168.3.0/24
  neighbor 10.0.5.1 route-map EXPORT-LOCAL out
  neighbor 10.0.6.1 route-map EXPORT-LOCAL out
 exit-address-family
!
line vty
!
""",
    }