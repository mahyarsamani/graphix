"""Specs for the stats SIFT adds to gem5.

graphix's built-in specs cover stock gem5 only.
These specs teach it the SIFT stats without touching the package:
pass them to `RunSet.from_dirs(..., specs=SIFT_SPECS)`.

| gem5 source | printed name | spec result |
|---|---|---|
| `CacheMemory.cc` | `usefulBytes.<accessor>` (also `read`, `write`, `resident`) | `UsefulBytes` histograms named `usefulBytes` (...), dim `accessor` |
| `CacheMemory.cc` | `bytesTransferred.<type>.<accessor>.<dst>` (current) | Scalar `bytesTransferred`, dims `type`, `accessor`, `dst` |
| `CacheMemory.cc` | `bytesTransferred[<label>][<dst>]` (runs before 2026-10) | Scalar `bytesTransferred`, dims `label`, `dst` |
| `Sequencer.cc` | `indRel{,Prod,Cons}AccLat.<consumer>[<producer>]<instance>` | Histogram `indRelAccLat`, dims `role`, `consumer`, `producer`, `instance` |
| `Sequencer.cc` | `hovLdindE2ELatency`, `hovLdindUnmatched`, `hovLdindStale` | Histogram and Scalars (current runs only) |

`dst` is gem5's MachineID string (`Cache_12`): the destination controller's
machine type and version.
The `dst` converter turns it into that controller's owner name, so transfers
can be grouped by where they went.
Runs before 2026-10-09 label every access `other` (see the SIFT memory).
"""

import re

import graphix as gx
from useful_bytes import UsefulBytes

CACHE = "gem5::ruby::CacheMemory"
SEQUENCER = "gem5::ruby::Sequencer"


def controller_owner(dst: str, run: gx.Run) -> str:
    """`Cache_12` -> the canonical owner name of controller version 12."""
    return run.canonical(run.controller(dst))[0]


USEFUL_BYTES = gx.StatSpec(
    re.compile(
        r"(?P<stat>usefulBytes|readUsefulBytes|writeUsefulBytes|residentUsefulBytes)"
        r"\.(?P<accessor>.+)"
    ),
    name="{stat}",
    owner_class=CACHE,
    kind=UsefulBytes,
    unit="Byte",
    reduce="merge",
    doc="Used bytes per evicted block, per accessor label",
)

BYTES_TRANSFERRED = gx.StatSpec(
    "bytesTransferred.{type}.{accessor}.{dst}",
    owner_class=CACHE,
    kind="scalar",
    dims={"dst": controller_owner},
    unit="Byte",
)

BYTES_TRANSFERRED_OLD = gx.StatSpec(
    "bytesTransferred[{label}][{dst}]",
    name="bytesTransferred",
    owner_class=CACHE,
    kind="scalar",
    dims={"label": lambda label: label or "demand", "dst": controller_owner},
    unit="Byte",
    doc="Pre-2026-10 naming: the label is an accessor or 'prefetch'",
)

# Since gem5 build v2 (2026-10-12) the latencies are Distributions in
# cycles with 8-cycle buckets up to 2048 and an overflow count; runs before
# that printed auto-sized Histograms in ticks, whose unit the run's own
# stats file carries (graphix keeps gem5's unit unless a spec overrides it).
IND_REL_LATENCY = gx.StatSpec(
    re.compile(
        r"indRel(?P<role>Prod|Cons|)AccLat\."
        r"(?P<consumer>[^.\[]+)\[(?P<producer>[^\]]*)\](?P<instance>\d*)"
    ),
    name="indRelAccLat",
    owner_class=SEQUENCER,
    kind="histogram",
    dims={
        "role": lambda role: {"": "overall", "Prod": "producer", "Cons": "consumer"}[role],
        "instance": lambda text: int(text) if text else 0,
    },
    plots=("cdf", "box"),
)

HOV = [
    gx.StatSpec("hovLdindE2ELatency", owner_class=SEQUENCER, kind="histogram", unit="Cycle"),
    gx.StatSpec("hovLdindUnmatched", owner_class=SEQUENCER, kind="scalar"),
    gx.StatSpec("hovLdindStale", owner_class=SEQUENCER, kind="scalar"),
]

# Per access name, since gem5 build v2: hits, misses and allocated bytes
# of every CacheMemory (`other` is an unlabelled access). hov accesses are
# named hov<p>_index and hov<p>_data by side-car entry p; the checkpoint
# manifest's `hov_entries` maps p to the index and data arrays.
PER_NAME = [
    gx.StatSpec(
        f"{family}.{{accessor}}",
        owner_class=CACHE,
        kind="scalar",
        unit=unit,
        doc=doc,
    )
    for family, unit, doc in [
        ("demandHits", "Count", "Demand hits per access name"),
        ("demandMisses", "Count", "Demand misses per access name"),
        ("prefetchHits", "Count", "Prefetch hits per access name"),
        ("prefetchMisses", "Count", "Prefetch misses per access name"),
        ("bytesAllocated", "Byte",
         "Bytes of blocks allocated (brought in and kept) per access name"),
    ]
]

SIFT_SPECS = [
    USEFUL_BYTES,
    BYTES_TRANSFERRED,
    BYTES_TRANSFERRED_OLD,
    IND_REL_LATENCY,
    *HOV,
    *PER_NAME,
]
