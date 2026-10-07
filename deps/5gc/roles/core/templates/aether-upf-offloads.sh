#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
#
# Turn off receive aggregation (GRO, hardware GRO, LRO) on the UPF's
# parent interfaces and on every device below them.
#
# Why: in af_packet mode the BESS UPF receives N6 (downlink) traffic
# through a macvlan on the parent interface. With receive aggregation on,
# the kernel merges consecutive TCP segments into one large packet (seen
# up to ~6.8 KB) before the UPF gets it. The UPF cannot GTP-U encapsulate
# a packet that size into a 1500-byte N3 frame and drops it without
# incrementing any counter, so downlink TCP collapses into retransmits
# (measured: ~2.5 Mbit/s with offloads on vs ~200 Mbit/s with them off).
#
# Aggregation happens where the packet is received (the lowest device,
# e.g. the physical or virtio NIC) and can be redone by GRO on stacked
# devices such as VLANs. Turning off only `gro`, or only `rx-gro-hw`, is
# not enough, and neither is touching only the top device: one of the
# remaining paths merges the packets again. So this walks
# /sys/class/net/<dev>/lower_* recursively and turns off every one of
# gro, rx-gro-hw and lro that the device supports and does not report as
# [fixed].
#
# Usage: aether-upf-offloads [--dry-run] IFACE...
#   --dry-run (or DRY_RUN=1) only reads the current state with
#   `ethtool -k` and prints the `ethtool -K` commands it would run.
#
# The settings do not survive a reboot or the interface being recreated,
# which is why aether-upf-offloads.service runs this at boot. Nothing
# turns the offloads back on; uninstalling Aether leaves them off until
# the interface is recreated or the host reboots.

set -u

dry_run="${DRY_RUN:-0}"
ifaces=()
count=0
for arg in "$@"; do
    case "$arg" in
        --dry-run|-n) dry_run=1 ;;
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        -*) echo "aether-upf-offloads: unknown option $arg" >&2; exit 2 ;;
        *) ifaces+=("$arg"); count=$((count + 1)) ;;
    esac
done

if [ "$count" -eq 0 ]; then
    echo "usage: aether-upf-offloads [--dry-run] IFACE..." >&2
    exit 2
fi

log() { echo "aether-upf-offloads: $*"; }

if ! command -v ethtool >/dev/null 2>&1; then
    log "ethtool not found" >&2
    exit 1
fi

# Collect each interface and, recursively, the devices below it.
devices=()
seen=" "
collect() {
    local dev="$1" lower
    case "$seen" in *" $dev "*) return ;; esac
    seen="$seen$dev "
    devices+=("$dev")
    for lower in /sys/class/net/"$dev"/lower_*; do
        [ -e "$lower" ] || continue
        collect "${lower##*/lower_}"
    done
}

rc=0
for iface in "${ifaces[@]}"; do
    if [ ! -e "/sys/class/net/$iface" ]; then
        log "$iface: no such interface" >&2
        rc=1
        continue
    fi
    collect "$iface"
done

# ethtool -k prints long names; map them to the -K short names.
feature_name() {
    case "$1" in
        gro) echo generic-receive-offload ;;
        lro) echo large-receive-offload ;;
        *) echo "$1" ;;
    esac
}

for dev in "${devices[@]}"; do
    if ! state="$(ethtool -k "$dev" 2>&1)"; then
        log "$dev: ethtool -k failed: $state" >&2
        rc=1
        continue
    fi
    for feat in gro rx-gro-hw lro; do
        line="$(printf '%s\n' "$state" | grep -m1 "^$(feature_name "$feat"):" || true)"
        value="${line#*: }"
        if [ -z "$line" ]; then
            log "$dev: $feat not supported, skipping"
        elif [ "${value#on}" != "$value" ] && [ "${value%\[fixed\]}" != "$value" ]; then
            log "$dev: $feat is on [fixed], cannot change" >&2
        elif [ "${value#on}" = "$value" ]; then
            log "$dev: $feat already $value"
        elif [ "$dry_run" = 1 ]; then
            log "$dev: $feat is on; would run: ethtool -K $dev $feat off"
        elif ethtool -K "$dev" "$feat" off; then
            log "$dev: $feat turned off"
        else
            log "$dev: ethtool -K $dev $feat off failed" >&2
            rc=1
        fi
    done
done

exit "$rc"
