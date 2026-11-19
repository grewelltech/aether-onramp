# 5gc

The 5gc repository builds a standalone Aether core with a physical RAN setup.
It depends on a k8s cluster, which can be deployed using the k8s repository to create a multi-node cluster.

To set up the 5gc repository, you need to provide the following:

1. Node configurations with IP addresses in the hosts.ini file.
   - You can specify both master and worker nodes.
2. Aether configuration parameters, such as the AMF address and the UPF's networks, in the `./vars/main.yml` file.

To download the 5gc repository, use the following command:
```
git clone https://github.com/omec-project/aether-5gc.git
```
To download the k8s repository used to provision the cluster, use:
```
git clone https://github.com/omec-project/aether-k8s.git
```
### Step-by-Step Installation
To install the 5g-core, follow these steps:
1. Set the configuration variables in the `vars/main.yml` file.
   - Set the "values_file" parameter:
      - Use "roles/core/templates/sdcore-5g-values.yaml" for a stateful 5g core.
      - Set `core.upf.mode` to `dpdk` when you want the built-in UPF rendered with SR-IOV, hugepages, and `vfioveth` networking.
   - The UPF's networking is described by `core.networks` and `core.upf.instances`. Both are optional; see [UPF networking](#upf-networking) below.
2. Add the hosts to `hosts.ini`.
3. Run `make ansible`.
4. In the running Ansible docker terminal:
   - Make sure you have deployed a k8s cluster using `k8s-install` from the k8s repo.
   - Run `make 5gc-install`.
   - It creates the host side of the UPF's networks (the `access` and `core` interfaces by default) using `5gc-router-install`.
   - Finally, it installs the 5g core using the values specified in `5gc-core-install`.
   - When a UPF's mode is `dpdk`, the core and additional UPF install roles validate that the interface its networks sit on has at least two VFs bound to the `vfio-pci` driver before deploying the UPF workload. The chart's SR-IOV device-plugin selector only exposes `vfio-pci`-bound VFs, so VFs bound to any other driver are ignored (they can never be allocated to the UPF pod).
      - If the access and core networks' `resource_name` values are different, the chart pins access/core to `vf 0` and `vf 1` specifically, so those two VFs must be bound to `vfio-pci` and have non-zero MAC addresses.
      - If they are the same, access/core share one SR-IOV resource pool whose selector exposes every `vfio-pci`-bound VF on the interface. The allocator may hand the UPF any of them, so **all** `vfio-pci`-bound VFs on the interface must have non-zero MAC addresses.
      - In dpdk mode both sides of a UPF must be on the same interface.
     - The installation process may take up to 3 minutes.

#### One-Step Installation
To install 5gc in one go, run `make 5gc-install`.
#### Uninstall
   - run `make 5gc-uninstall`

### UPF networking

The UPF (User Plane Function) carries the UEs' traffic. It has two network
interfaces, called its two *sides*:

- **access** (3GPP N3) faces the radio network. gNBs send each UE's traffic to
  the UPF's access address inside GTP-U tunnels (UDP port 2152), and the UPF
  sends downlink traffic back to the gNBs from it.
- **core** (3GPP N6) faces the data network: the Internet or your own servers.
  Traffic leaves and arrives here as ordinary IP packets carrying the UE's
  address.

Two keys in `vars/main.yml` describe this, and both are optional:

- `core.networks` describes the networks the sides plug into: which host
  interface each one is on, its subnet, and which router serves it.
- `core.upf.instances` lists the UPFs, and for each one the network and address
  of each side and the address pool its UEs get.

#### The default

With neither key set, OnRamp builds what it has always built:

| | access side (N3) | core side (N6) |
|---|---|---|
| Host interface | the interface carrying the server's default route (`ens18` in these examples) | the same interface |
| Subnet | `192.168.252.0/24` | `192.168.250.0/24` |
| Router | this server, at `192.168.252.1` on a macvlan interface named `access` | this server, at `192.168.250.1` on a macvlan interface named `core` |
| UPF address | `192.168.252.3` | `192.168.250.3` |

UEs get addresses from `192.168.100.0/24`. The server routes that pool to the
UPF's core address and masquerades (NATs) it when it leaves through the
default-route interface, so UEs can reach the Internet. The UPF sends downlink
traffic for the gNBs to the server, which forwards it onto the server's LAN; a
gNB on that LAN reaches the UPF with a route to `192.168.252.0/24` via the
server's address.

Written out in full, the default is the following. You never need to write it;
on a server whose default route is on `ens18`, leaving both keys out has
exactly this effect:

```yaml
core:
  networks:
    access:
      iface: ens18               # the interface carrying the default route
      subnet: 192.168.252.0/24
      gateway: host              # this server is the router, at 192.168.252.1
      ran_subnet: ""             # the gNBs are on ens18's own subnet (the server's LAN)
    core:
      iface: ens18
      subnet: 192.168.250.0/24
      gateway: host              # this server is the router, at 192.168.250.1
  upf:
    instances:
      default:
        access: { network: access, ip: 192.168.252.3 }
        core: { network: core, ip: 192.168.250.3 }
        ue_ip_pool: 192.168.100.0/24
```

The shipped `vars/main.yml` sets only two of these values: `ran_subnet:
"172.20.0.0/16"`, because gNBsim's simulated gNBs sit on that subnet, and the
UE pool.

The install prints the resolved result ("show the resolved UPF networking")
before anything is deployed, so you can check what the defaults decided.

#### Changing what differs

Set only what differs from the default. To keep everything above but use a
different interface, for example `eno1`, name it for both networks:

```yaml
core:
  networks:
    access: { iface: eno1 }
    core: { iface: eno1 }
```

The addresses, the routing and the NAT stay as in the default, now on `eno1`.
Keep the shipped `ran_subnet: "172.20.0.0/16"` under `access` if you run
gNBsim; for gNBs on `eno1`'s own LAN, leave it out. If `eno1` does not carry
the default route, a `ran_subnet` left empty is taken from `eno1`'s own subnet,
and UE traffic is NATed on both `eno1` and the default-route interface, leaving
by whichever one the server's routing table picks.

To change one side only, name just that side. For example, suppose the server has a
second NIC, `eno2`, cabled to a site router at `10.60.0.1` that leads to the
Internet, and UE traffic should leave through that router instead of through
this server:

```yaml
core:
  networks:
    core:
      iface: eno2
      subnet: 10.60.0.0/24
      gateway: 10.60.0.1
```

The access side keeps its default. On the core side:

- the UPF's core address is `10.60.0.3`, on `eno2`, and its default route is
  via `10.60.0.1`;
- because the gateway is an address rather than `host`, this server configures
  nothing for the core network: no `core` interface, no route to the UE pool
  and no NAT;
- so the router at `10.60.0.1` must route the UE pool (`192.168.100.0/24`) to
  `10.60.0.3`, and NAT it if UEs should reach the Internet.

#### Network fields

Each entry in `core.networks` is keyed by the network's name. `access` and
`core` are the networks the built-in UPF uses; other names are only needed for
additional UPFs. All fields are optional:

| field | default | meaning |
|---|---|---|
| `iface` | the interface carrying the default route | the host interface the network is on |
| `vlan` | none | an 802.1Q VLAN ID; the UPF then attaches to `<iface>.<vlan>`, which `5gc-router-install` creates |
| `subnet` | `192.168.252.0/24` for `access`, `192.168.250.0/24` for `core` | the network's subnet; required for any other network |
| `gateway` | `host` | the network's router. `host` makes this server the router, at the subnet's first address: it creates a macvlan interface named after the network, forwards between it and `iface`, routes each UPF's UE pool to that UPF and NATs the pools on the way out. An IP address names an external router instead, and this server configures nothing for the network. |
| `attach` | `macvlan` | how the UPF attaches to `iface` in `af_packet` mode. `macvlan` shares the interface with the host; `host-device` moves the whole interface into the UPF pod, so the host loses it while the UPF runs and the gateway must be an external router. |
| `resource_name` | `intel.com/intel_sriov_vfio_access` / `_core` | the SR-IOV resource pool in `dpdk` mode; required for any other network |
| `ran_subnet` | the subnet of `iface`'s own address | access networks only: where the gNBs are. The UPF sends downlink traffic for this subnet to the network's gateway. Set it when the gNBs are not on `iface`'s own subnet (gNBsim's `172.20.0.0/16`, or a routed RAN site), or when `attach: host-device` takes the interface off the host. |

#### UPF instances

Each entry in `core.upf.instances` is one UPF, keyed by its name.

- `default` is the UPF installed with the core. It always exists, whether or
  not it is listed.
- Any other name is an additional UPF. `make aether-add-upfs` installs each one
  as its own `bess-upf` Helm release, in namespace `aether-upf-<name>`.

An instance has these fields:

| field | default | meaning |
|---|---|---|
| `access.network` | `access` | the network (a name in `core.networks`) the UPF's access side is on |
| `access.ip` | the third address of that network's subnet (`.3`) | the UPF's access address |
| `core.network` | `core` | the network the UPF's core side is on |
| `core.ip` | the third address of that network's subnet | the UPF's core address |
| `ue_ip_pool` | `192.168.100.0/24` for `default`; required for any other UPF | the addresses this UPF's UEs get; pools must not overlap |
| `mode` | `core.upf.mode` | `af_packet` or `dpdk` |

A second UPF on the same networks as the built-in one, as in
`vars/main-upf.yml`. It names no networks, so it uses `access` and `core`, and
it needs addresses other than the built-in UPF's `.3`:

```yaml
core:
  upf:
    instances:
      default:
        ue_ip_pool: "192.168.100.0/24"
      "1":
        access: { ip: "192.168.252.6" }
        core: { ip: "192.168.250.6" }
        ue_ip_pool: "192.168.101.0/24"
```

A second UPF on networks of its own. Its access side is on `eno3`, with this
server as the router; its core side is on `eno4`, behind a router at
`10.80.0.1`, which must route `192.168.102.0/24` to `10.80.0.5`:

```yaml
core:
  networks:
    n3b: { iface: eno3, subnet: 10.70.0.0/24 }
    n6b: { iface: eno4, subnet: 10.80.0.0/24, gateway: 10.80.0.1 }
  upf:
    instances:
      edge-2:
        access: { network: n3b, ip: 10.70.0.5 }
        core: { network: n6b, ip: 10.80.0.5 }
        ue_ip_pool: 192.168.102.0/24
```

To add UPFs, list them and run `make aether-add-upfs`. It runs
`5gc-router-install`, which builds any network the new UPFs need, then
`5gc-upf-install`. When a UPF's core network has `gateway: host`, its UE pool
route and NAT are installed as `aether-upf-<name>-routes.service`.

To remove one:

1. Run `make aether-remove-upfs` while it is still listed. This removes every
   additional UPF in `core.upf.instances`, with its route and NAT unit.
2. Delete its entry.
3. Run `make aether-add-upfs` to reinstall the remaining additional UPFs and
   take down any network no UPF uses any more.

#### What the install refuses

The install stops before deploying a configuration that cannot work: a gateway
outside its subnet, `attach: host-device` with `gateway: host`, moving the
interface that carries the server's default route (or anything beneath it) into
a pod, a network used by both a `dpdk` and an `af_packet` UPF, two UPFs sharing
an address, overlapping UE pools, unknown keys, and the keys this section
replaced (the message names each one's replacement). In `dpdk` mode both sides
of a UPF must be on the same interface, and `attach` does not apply.
