# Knobs added on this branch

This branch (`infosite/knobs`) adds configuration knobs to Aether OnRamp for the
aether-sdcore-infosite reference deployments. Every knob defaults to upstream
behavior, so an unchanged `vars/main.yml` deploys exactly what upstream does.
Each knob is its own commit, written as a candidate upstream PR.

To see everything that differs from upstream:

```
git fetch upstream   # https://github.com/opennetworkinglab/aether-onramp
git diff upstream/main...infosite/knobs
git log --oneline upstream/main..infosite/knobs
```

| Knob | Default (upstream behavior) | What it enables | Related issue |
|---|---|---|---|
| `core.upf.access_iface`, `core.upf.core_iface` | `core.data_iface` (after default-route derivation) | Put the UPF's N3 and N6 macvlans on different NICs/VLANs | ONR-21 |
| `core.router.enabled` | `true` | Skip the host router (host macvlans, UE-pool route, FORWARD rules, UE NAT) when the site network routes N3/N6 and does NAT at its edge | ONR-16, ONR-22 |
| `core.helm.extra_values_files` | `[]` | Extra values files for the SD-Core chart, applied after `core.values_file` | ONR-19 |
| `ueransim.servers[n].ngap_ip`, `gtp_ip`, `link_ip`, `nci`, `supi` | `ueransim.gnb.ip`, `0x000000010`, `imsi-001010100007510` | Separate N2/N3 addresses per gNB, and distinct identities per UERANSIM node | ONR-23 |

## Fixes (candidate upstream PRs)

Bug fixes rather than knobs. Each sits on its own branch based on
`upstream/main`, and this branch is rebased on top of it.

| Fix | Branch | What it fixes |
|---|---|---|
| Resolve `data_iface` into `core_data_iface` / `gnbsim_data_iface` | `fix/data-iface-derivation` | Deriving `core.data_iface` and `gnbsim.router.data_iface` from the default-route interface never took effect. The Makefiles pass `vars/main.yml` as `--extra-vars`, which outrank `set_fact`, so leaving the value at `""` or `data` failed validation. The 5gc core, upf and router roles and the gnbsim router and docker roles now resolve into new facts and read those. |

Issue IDs refer to `research/ISSUES.md` in
https://github.com/grewelltech/aether-sdcore-infosite.
