#!/usr/bin/env python3
"""Derive the OFH and DU-High CPU placement from an isolated CPU set.

Prints one JSON object on stdout:

    {"isolated": [30, 31, 32, 33], "timing_cpu": 30, "txrx_cpu": 31,
     "du_high_cpus": "32-33", "housekeeping": "0-29,34-95", "usable": true}

The isolated set is any Linux CPU list, so "28-55,84-111" -- a NUMA node's
CPUs together with their SMT siblings -- works as well as a single "5-26"
range. `usable` is false when there are fewer than four isolated CPUs, which
is the point below which there is nothing left for the DU-High pool after the
OFH timing and TX/RX threads.

`housekeeping` is every online CPU that is not isolated, for irqaffinity.
"""
import json
import pathlib
import sys

ONLINE = pathlib.Path("/sys/devices/system/cpu/online")


def expand(spec):
    """Expands a Linux CPU list ("0-3,8,12-13") into a sorted list of ints."""
    cpus = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            first, last = part.split("-")[:2]
            cpus.update(range(int(first), int(last) + 1))
        else:
            cpus.add(int(part))
    return sorted(cpus)


def compact(cpus):
    """Renders a sorted list of ints as a Linux CPU list."""
    runs = []
    for cpu in cpus:
        if runs and cpu == runs[-1][1] + 1:
            runs[-1][1] = cpu
        else:
            runs.append([cpu, cpu])
    return ",".join(
        str(first) if first == last else f"{first}-{last}" for first, last in runs
    )


def main(argv):
    if len(argv) != 2:
        print("usage: dpdk-cpu-plan.py <isolated-cpus>", file=sys.stderr)
        return 2
    try:
        isolated = expand(argv[1])
    except ValueError:
        print(f"cannot parse the isolated CPU set {argv[1]!r}", file=sys.stderr)
        return 1

    result = {
        "isolated": isolated,
        "timing_cpu": None,
        "txrx_cpu": None,
        "du_high_cpus": "",
        "housekeeping": "",
        "usable": len(isolated) >= 4,
    }
    if result["usable"]:
        result["timing_cpu"] = isolated[0]
        result["txrx_cpu"] = isolated[1]
        result["du_high_cpus"] = compact(isolated[2:])

    try:
        online = expand(ONLINE.read_text().strip())
    except (OSError, ValueError):
        online = []
    if online:
        result["housekeeping"] = compact(sorted(set(online) - set(isolated)))

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
