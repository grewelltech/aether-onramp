#!/usr/bin/env python3
"""Report the fronthaul NIC's NUMA node and whether the isolated CPUs share it.

Prints one JSON object on stdout:

    {"pf": "ens6f0np0", "node": 1, "cpulist": "28-55,84-111",
     "stray": [5, 6], "free_1g": 1, "nof_nodes": 2}

`node` is -1 when the device reports no node, which is what a single-socket
host and a firmware that omits the ACPI locality both look like; callers treat
that as "nothing to align". `stray` lists the isolated CPUs that are *not* on
the device's node, so an empty list means the pinning and the NIC agree.

Read-only: it only reads sysfs.
"""
import json
import pathlib
import sys

NODE_ROOT = pathlib.Path("/sys/devices/system/node")
HUGE_1G = "hugepages/hugepages-1048576kB/free_hugepages"


def expand(spec):
    """Expands a Linux CPU list ("0-3,8,12-13") into a set of ints."""
    cpus = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            first, last = part.split("-")[:2]
            cpus.update(range(int(first), int(last) + 1))
        else:
            cpus.add(int(part))
    return cpus


def read_int(path):
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def main(argv):
    if len(argv) != 3:
        print("usage: dpdk-numa-probe.py <pf-iface> <isolated-cpus>", file=sys.stderr)
        return 2
    pf, isolated = argv[1], argv[2]

    result = {
        "pf": pf,
        "node": -1,
        "cpulist": "",
        "stray": [],
        "free_1g": None,
        "nof_nodes": len(sorted(NODE_ROOT.glob("node[0-9]*"))),
    }

    node = read_int(pathlib.Path("/sys/class/net") / pf / "device" / "numa_node")
    if node is None or node < 0:
        print(json.dumps(result))
        return 0
    result["node"] = node

    node_dir = NODE_ROOT / f"node{node}"
    try:
        result["cpulist"] = node_dir.joinpath("cpulist").read_text().strip()
    except OSError:
        result["cpulist"] = ""
    result["free_1g"] = read_int(node_dir / HUGE_1G)

    if result["cpulist"]:
        try:
            result["stray"] = sorted(expand(isolated) - expand(result["cpulist"]))
        except ValueError:
            # An isolated_cpus that does not parse is the pinning task's
            # problem to report, not this probe's.
            result["stray"] = []

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
