#!/usr/bin/env bash
# =============================================================================
# sdwan lab - FRR routers with eBGP + Alpine hosts, deployed with Containerlab
# Follows the structure of Brian Linkletter's FRR/Containerlab guide:
#   1. one directory per router with a "daemons" file and an "frr.conf" file
#   2. a topology file that bind-mounts those two files into each router
#   3. "clab deploy"
#   4. host interfaces/routes configured with "docker exec ... ip ..."
# The only change vs. the guide: OSPF is replaced by eBGP (bgpd instead of ospfd).
#
# Usage:  ./lab.sh          (build configs + deploy + configure hosts + ping tests)
#         ./lab.sh test     (only run the ping tests)
#         ./lab.sh down     (destroy the lab)
# =============================================================================
set -u

[ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
cd "$(dirname "$(readlink -f "$0")")" || exit 1

LAB=sdwan
TOPO=${LAB}.clab.yml
FRR_IMAGE=quay.io/frrouting/frr:10.0.1
HOST_IMAGE=alpine:latest
CLAB=$(command -v clab || command -v containerlab) || { echo "containerlab not found"; exit 1; }

c() { echo "clab-${LAB}-$1"; }   # container name helper

# -----------------------------------------------------------------------------
# Addressing plan
#
#  AS numbers : isp1=65001  isp2=65002  edge-a=65101  edge-b=65102  edge-c=65103
#  Loopbacks  : isp1 10.10.10.1  isp2 10.10.10.2  edge-a/b/c 10.10.10.11/12/13 (/32)
#
#  Link                        Subnet         ISP side   Edge side
#  edge-a:eth1 - isp1:eth1     10.0.1.0/30    .1         .2
#  edge-a:eth2 - isp2:eth1     10.0.2.0/30    .1         .2
#  edge-b:eth1 - isp1:eth2     10.0.3.0/30    .1         .2
#  edge-b:eth2 - isp2:eth2     10.0.4.0/30    .1         .2
#  edge-c:eth1 - isp1:eth4     10.0.5.0/30    .1         .2
#  edge-c:eth2 - isp2:eth4     10.0.6.0/30    .1         .2
#  isp1:eth3   - isp2:eth3     10.0.0.0/30    isp1 .1    isp2 .2
#  host-a - edge-a:eth3        192.168.1.0/24 edge .1    host .2
#  host-b - edge-b:eth3        192.168.2.0/24 edge .1    host .2
#  host-c - edge-c:eth3        192.168.3.0/24 edge .1    host .2
# -----------------------------------------------------------------------------

destroy_lab() { "$CLAB" destroy --topo "$TOPO" --cleanup; }

# -----------------------------------------------------------------------------
# Step 1 - topology file (fixed YAML: "binds", no trailing commas, quoted-free image)
# -----------------------------------------------------------------------------
write_topology() {
  cat > "$TOPO" <<EOF
name: ${LAB}

topology:
  nodes:
    isp1:
      kind: linux
      image: ${FRR_IMAGE}
      binds:
        - isp1/daemons:/etc/frr/daemons
        - isp1/frr.conf:/etc/frr/frr.conf
    isp2:
      kind: linux
      image: ${FRR_IMAGE}
      binds:
        - isp2/daemons:/etc/frr/daemons
        - isp2/frr.conf:/etc/frr/frr.conf
    edge-a:
      kind: linux
      image: ${FRR_IMAGE}
      binds:
        - edge-a/daemons:/etc/frr/daemons
        - edge-a/frr.conf:/etc/frr/frr.conf
    edge-b:
      kind: linux
      image: ${FRR_IMAGE}
      binds:
        - edge-b/daemons:/etc/frr/daemons
        - edge-b/frr.conf:/etc/frr/frr.conf
    edge-c:
      kind: linux
      image: ${FRR_IMAGE}
      binds:
        - edge-c/daemons:/etc/frr/daemons
        - edge-c/frr.conf:/etc/frr/frr.conf
    host-a:
      kind: linux
      image: ${HOST_IMAGE}
    host-b:
      kind: linux
      image: ${HOST_IMAGE}
    host-c:
      kind: linux
      image: ${HOST_IMAGE}

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
EOF
}

# -----------------------------------------------------------------------------
# Step 2 - "daemons" files: standard FRR file from the image, with bgpd enabled
# (the guide enables zebra + ospfd; here zebra + bgpd, ospfd/ldpd stay off)
# -----------------------------------------------------------------------------
write_daemons() {
  local tmpl
  tmpl=$(docker run --rm --entrypoint cat "$FRR_IMAGE" /etc/frr/daemons) || {
    echo "Could not extract the default daemons file from $FRR_IMAGE"; exit 1; }
  for r in isp1 isp2 edge-a edge-b edge-c; do
    mkdir -p "$r"
    printf '%s\n' "$tmpl" | sed -e 's/^bgpd=no/bgpd=yes/' > "$r/daemons"
    chmod 644 "$r/daemons"
  done
}

# -----------------------------------------------------------------------------
# Step 3 - frr.conf per router (interfaces + eBGP), same layout as the guide
# -----------------------------------------------------------------------------
write_isp_confs() {
  cat > isp1/frr.conf <<'EOF'
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
EOF

  cat > isp2/frr.conf <<'EOF'
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
EOF
}

# Edge routers are customers of both ISPs: they only announce their OWN prefixes
# (AS-path ^$ = locally originated) so they never become a transit between isp1/isp2.
write_edge_confs() {
  cat > edge-a/frr.conf <<'EOF'
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
EOF

  cat > edge-b/frr.conf <<'EOF'
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
EOF

  cat > edge-c/frr.conf <<'EOF'
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
EOF
  chmod 644 isp1/frr.conf isp2/frr.conf edge-a/frr.conf edge-b/frr.conf edge-c/frr.conf
}

# -----------------------------------------------------------------------------
# Step 4 - hosts (equivalent of the guide's PC-interfaces script)
# -----------------------------------------------------------------------------
config_host() {   # <host> <ip/mask> <gateway>
  local ct; ct=$(c "$1")
  docker exec "$ct" ip link set eth1 up
  docker exec "$ct" ip addr add "$2" dev eth1
  docker exec "$ct" ip route add 192.168.0.0/16 via "$3" dev eth1   # other LANs
  docker exec "$ct" ip route add 10.0.0.0/8     via "$3" dev eth1   # links + loopbacks
}

config_hosts() {
  config_host host-a 192.168.1.2/24 192.168.1.1
  config_host host-b 192.168.2.2/24 192.168.2.1
  config_host host-c 192.168.3.2/24 192.168.3.1
}

# -----------------------------------------------------------------------------
# Step 5 - wait for BGP and test
# -----------------------------------------------------------------------------
vt() { docker exec "$(c "$1")" vtysh -c "$2"; }

wait_for_bgp() {
  echo ">> Waiting for BGP to converge (max 90 s)..."
  for _ in $(seq 1 45); do
    if docker exec "$(c host-a)" ping -c1 -W1 192.168.2.2 >/dev/null 2>&1 &&
       docker exec "$(c host-a)" ping -c1 -W1 192.168.3.2 >/dev/null 2>&1 &&
       docker exec "$(c host-b)" ping -c1 -W1 192.168.3.2 >/dev/null 2>&1; then
      echo ">> Converged."; return 0
    fi
    sleep 2
  done
  echo ">> Not fully converged yet - check with: docker exec $(c isp1) vtysh -c 'show bgp summary'"
  return 1
}

p() {   # <src-host> <dst-ip> <label>
  if docker exec "$(c "$1")" ping -c2 -W2 "$2" >/dev/null 2>&1; then
    printf '  [ OK ] %-7s -> %-14s %s\n' "$1" "$2" "$3"
  else
    printf '  [FAIL] %-7s -> %-14s %s\n' "$1" "$2" "$3"
  fi
}

run_tests() {
  echo ">> BGP sessions"
  for r in isp1 isp2 edge-a edge-b edge-c; do
    echo "--- $r"; vt "$r" "show bgp summary" | sed -n '/Neighbor/,$p'
  done
  echo ">> Ping tests"
  p host-a 192.168.2.2 "host-b"
  p host-a 192.168.3.2 "host-c"
  p host-b 192.168.1.2 "host-a"
  p host-b 192.168.3.2 "host-c"
  p host-c 192.168.1.2 "host-a"
  p host-c 192.168.2.2 "host-b"
  p host-a 10.10.10.1  "isp1 loopback"
  p host-a 10.10.10.2  "isp2 loopback"
  p host-a 10.10.10.12 "edge-b loopback"
  p host-c 10.10.10.11 "edge-a loopback"
  p host-a 10.0.4.1    "isp2 <-> edge-b link"
  p host-b 10.0.0.2    "isp1-isp2 link"
  echo ">> Path host-a -> host-c:"
  docker exec "$(c host-a)" traceroute -n -w1 192.168.3.2 2>/dev/null || true
}

# -----------------------------------------------------------------------------
case "${1:-up}" in
  down) destroy_lab ;;
  test) run_tests ;;
  up)
    write_topology
    write_daemons
    write_isp_confs
    write_edge_confs
    "$CLAB" deploy --topo "$TOPO" --reconfigure
    for r in isp1 isp2 edge-a edge-b edge-c; do      # make sure the routers forward
      docker exec "$(c "$r")" sysctl -qw net.ipv4.ip_forward=1 2>/dev/null || true
    done
    config_hosts
    wait_for_bgp
    run_tests
    ;;
  *) echo "Usage: $0 [up|test|down]"; exit 1 ;;
esac
