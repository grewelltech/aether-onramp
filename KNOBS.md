# Knobs added on this branch

This branch (`infosite/knobs-c01b508`, rebased onto upstream c01b508) adds configuration knobs to Aether OnRamp for the
aether-sdcore-infosite reference deployments. Every knob defaults to upstream
behavior, so an unchanged `vars/main.yml` deploys exactly what upstream does.
Each knob is its own commit, written as a candidate upstream PR.

To see everything that differs from upstream:

```
git fetch upstream   # https://github.com/opennetworkinglab/aether-onramp
git diff upstream/main...infosite/knobs-c01b508
git log --oneline upstream/main..infosite/knobs-c01b508
```

| Knob | Default (upstream behavior) | What it enables | Related issue |
|---|---|---|---|
| `core.upf.access_iface`, `core.upf.core_iface` | `core.data_iface` (after default-route derivation) | Put the UPF's N3 and N6 macvlans on different NICs/VLANs | ONR-21 |
| `core.router.enabled` | `true` | Skip the host router (host macvlans, UE-pool route, FORWARD rules, UE NAT) when the site network routes N3/N6 and does NAT at its edge. Does not affect the UPF receive-offload fix below, which the core role installs | ONR-16, ONR-22 |
| `core.helm.extra_values_files` | `[]` | Extra values files for the SD-Core chart, applied after `core.values_file` | ONR-19 |
| `ueransim.servers[n].ngap_ip`, `gtp_ip`, `link_ip`, `nci`, `supi` | `ueransim.gnb.ip`, `0x000000010`, `imsi-001010100007510` | Separate N2/N3 addresses per gNB, and distinct identities per UERANSIM node | ONR-23 |

## Fixes (candidate upstream PRs)

Bug fixes rather than knobs. Each sits on its own branch based on
`upstream/main`, and this branch is rebased on top of it.

| Fix | Branch | What it fixes |
|---|---|---|
| Resolve `data_iface` into `core_data_iface` / `gnbsim_data_iface` | `fix/data-iface-derivation-c01b508` | Deriving `core.data_iface` and `gnbsim.router.data_iface` from the default-route interface never took effect. The Makefiles pass `vars/main.yml` as `--extra-vars`, which outrank `set_fact`, so leaving the value at `""` or `data` failed validation. The 5gc core, upf and router roles and the gnbsim router and docker roles now resolve into new facts and read those. |
| Keep GRO/LRO off on the UPF parent interfaces | `fix/upf-receive-offloads` (depends on `fix/data-iface-derivation-c01b508`) | The af_packet UPF silently drops packets that receive aggregation has merged beyond the N3 MTU, so downlink TCP collapses (measured ~2.5 Mbit/s vs ~200 Mbit/s). Upstream only ran a one-shot `ethtool -K <data_iface> gro off` from the router role: lost on reboot, left `rx-gro-hw`/LRO on, missed the devices under a VLAN, and was skipped entirely with `core.router.enabled: false`. The core role now installs `aether-upf-offloads.service`, which at boot and on every install turns off `gro`, `rx-gro-hw` and `lro` on each UPF parent interface (`core.upf.access_iface` and `core.upf.core_iface` on this branch) and every device below it. Uninstall removes the unit but leaves the offloads off until reboot. |
| Keep the Multus CNI config across reboots | `fix/multus-config-persist-c01b508` | RKE2's rke2-multus chart defaults to `cleanupConfigOnExit: true`, which deletes `/etc/cni/net.d/00-multus.conf` at shutdown. At the next boot the kubelet rebuilds pod sandboxes as soon as Canal's conflist is found, before the Multus pod has rewritten its config, so the UPF comes back with only `eth0` (no `access`/`core` macvlans) and `bess-init` loops on a missing route until the pod is deleted. The rke2 role now installs a `HelmChartConfig` for rke2-multus with `cleanupConfigOnExit: false` and `readinessIndicatorFile` set to Canal's conflist. RKE2 enabled the cleanup for the kubeconfig token refresh loop (rancher/rke2#9313), which OnRamp does not need (no CIS profile: tokens live a year and are re-issued when the Multus pod starts). |

Issue IDs refer to `research/ISSUES.md` in
https://github.com/grewelltech/sdcore-lab.
