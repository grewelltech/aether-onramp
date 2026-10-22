# 5gc

The 5gc repository builds a standalone Aether core with a physical RAN setup.
It depends on a k8s cluster, which can be deployed using the k8s repository to create a multi-node cluster.

To set up the 5gc repository, you need to provide the following:

1. Node configurations with IP addresses in the hosts.ini file.
   - You can specify both master and worker nodes.
2. Aether configuration parameters, such as `data_iface`, in the `./vars/main.yml` file.

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
   - Specify the "data_iface" parameter as the network interface name of the machine.
   - Set the "values_file" parameter:
      - Use "roles/core/templates/sdcore-5g-values.yaml" for a stateful 5g core.
      - Set `core.upf.mode` to `dpdk` when you want the built-in UPF rendered with SR-IOV, hugepages, and `vfioveth` networking.
   - If the `core.ran_subnet` parameter is left empty, the core will use the subnet of "data_iface" for UPF.
2. Add the hosts to `hosts.ini`.
3. Run `make ansible`.
4. In the running Ansible docker terminal:
   - Make sure you have deployed a k8s cluster using `k8s-install` from the k8s repo.
   - Run `make 5gc-install`.
   - It creates networking interfaces for UPF, such as access/core, using `5gc-router-install`.
   - Finally, it installs the 5g core using the values specified in `5gc-core-install`.
   - When `core.upf.mode` is set to `dpdk`, the core and additional UPF install roles validate that `core.data_iface` has at least two VFs bound to the `vfio-pci` driver before deploying the UPF workload. The chart's SR-IOV device-plugin selector only exposes `vfio-pci`-bound VFs, so VFs bound to any other driver are ignored (they can never be allocated to the UPF pod).
      - If `core.upf.access_resource_name` and `core.upf.core_resource_name` are different, the chart pins access/core to `vf 0` and `vf 1` specifically, so those two VFs must be bound to `vfio-pci` and have non-zero MAC addresses.
      - If `core.upf.access_resource_name` and `core.upf.core_resource_name` are the same, access/core share one SR-IOV resource pool whose selector exposes every `vfio-pci`-bound VF on `core.data_iface`. The allocator may hand the UPF any of them, so **all** `vfio-pci`-bound VFs on the interface must have non-zero MAC addresses.
   - The UPF's access (N3) side attaches to `core.data_iface`. Set `core.data_iface_n6` to put the core (N6) side on a second interface, and `core.upf.access_cni_plugin` / `core.upf.core_cni_plugin` to choose how each side attaches. Unset, both sides share `core.data_iface` with the plugin they use today, which is the collapsed deployment.
      - `macvlan` creates a virtual child of the named interface, so several pods can share it. `host-device` moves the named interface into the UPF pod instead, which is what makes the two planes genuinely separate L2 domains — and means each side needs an interface of its own.
      - `core.data_iface` keeps its other meanings: it is the interface `core.ran_subnet` is derived from, and the one the SR-IOV VF preflight validates in `dpdk` mode. Only the UPF's N6 attachment moves.
      - **Only the UPF pod's attachment moves. The host side of N6 does not.** `5gc-router-install` builds the UPF's N6 next hop as a macvlan child of `core.data_iface` carrying `core.upf.core_subnet`'s address, forwards between that child and `core.data_iface`, and masquerades the UE pool out `core.data_iface`. Moving the UPF's N6 attachment to another interface puts the pod on a different L2 domain from that gateway, so a deployment that sets `core.data_iface_n6` must provide the N6 gateway and egress itself, on the N6 segment. Note that `make aether-5gc-install` and `make aether-install` both resolve to `5gc-install`, which runs `5gc-router-install`.
      - This affects the built-in UPF only. Additional UPFs (`core.upf.additional_upfs`, deployed by the `5gc/upf` role) render their own values and are unchanged by these settings.
      - The install rejects five combinations before deploying: the N6 interface absent from the host; `host-device` with both sides on one interface (a moved device serves one side only, so the pod never starts); `host-device` on the interface carrying the host's default route; `host-device` while `core.upf.mode` is `dpdk`; and a separate N6 interface while `core.upf.mode` is `dpdk`, since the VF preflight validates `core.data_iface` only.
     - The installation process may take up to 3 minutes.

#### One-Step Installation
To install 5gc in one go, run `make 5gc-install`.
#### Uninstall
   - run `make 5gc-uninstall`
