"""Specs for the stats SIFT adds to gem5.

graphix's built-in specs cover stock gem5 only.
These specs teach it the SIFT stats without touching the package:
pass them to `RunSet.from_dirs(..., specs=SIFT_SPECS)`.

| gem5 source | printed name | spec result |
|---|---|---|
| `CacheMemory.cc` | `usefulBytes.<accessor>` (also `read`, `write`, `resident`, `invalidated`, `droppedEvict`) | `UsefulBytes` histograms named `usefulBytes` (...), dim `accessor` |
| `CacheMemory.cc` | `{,resident}{lifetimeUsefulBytes,crossCoreUsefulBytes,lifetimeShared}.<accessor>` | `UsefulBytes` (bytes) and Histogram (shared), dims `when` (`left`, `resident`), `accessor` |
| `CacheMemory.cc` | `bytesTransferred.<type>.<accessor>.<dst>` (current) | Scalar `bytesTransferred`, dims `type`, `accessor`, `dst` |
| `CacheMemory.cc` | `bytesTransferred[<label>][<dst>]` (runs before 2026-10) | Scalar `bytesTransferred`, dims `label`, `dst` |
| `Sequencer.cc` | `indRel{,Prod,Cons}AccLat.<consumer>[<producer>]<instance>` | Histogram `indRelAccLat`, dims `role`, `consumer`, `producer`, `instance` |
| `Sequencer.cc` | `hovLdindE2ELatency`, `hovLdindUnmatched`, `hovLdindStale` | Histogram and Scalars (current runs only) |
| `Sequencer.cc` | `hovValueChecks`, `hovValueMismatches`, `hovIndexChecks`, `hovIndexMismatches`, `hovChecksUnchecked` | Scalars (build v2) |
| `CacheMemory.cc` | `{demand,prefetch,index,idr,gather}{Hits,Misses}.<accessor>`, `bytesAllocated.<accessor>` | Scalars, dim `accessor` (build v2) |
| `base.cc` (O3 commit) | `commitStats<t>.committed{Loads,Stores}.<accessor>` | Scalars `committedLoads`, `committedStores`, dims `thread`, `accessor` (build v2) |
| `indirect_memory.cc` | `imp.<counter>`, `imp.patternsEnabled::shift<s>`, `imp.indirectDistance` | Scalars, a Vector (element dim `shift`) and a Histogram on IndirectMemory prefetchers (WP3 build) |
| `queued.cc` | `pfTranslationFailed` (nozero) | Scalar on Queued prefetchers (WP3 build) |

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
        r"(?P<stat>usefulBytes|readUsefulBytes|writeUsefulBytes"
        r"|residentUsefulBytes|invalidatedUsefulBytes|droppedEvictUsefulBytes)"
        r"\.(?P<accessor>.+)"
    ),
    name="{stat}",
    owner_class=CACHE,
    kind=UsefulBytes,
    unit="Byte",
    reduce="merge",
    doc="Used bytes per block, per accessor label: replaced (usefulBytes "
    "and its read and write parts), still resident at the dump "
    "(residentUsefulBytes), or invalidated without a replacement "
    "(invalidatedUsefulBytes); droppedEvictUsefulBytes: bytes used upstream "
    "of an eviction that reached a cache not holding the block",
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
    # The same latency split by how the uop0's DAG reached the Gather Unit
    # (gem5 2026-10-15): its own LDIDX, merged into the drain-time
    # notification of a line in flight, or a NotifyIndIdxReq (forwarded in
    # the LSQ, or the register form); the three sum to the total.
    gx.StatSpec(
        re.compile(r"hovLdindE2ELatency(?P<kind>Leader|Merged|Notified)"),
        name="hovLdindE2ELatencyByKind",
        owner_class=SEQUENCER,
        kind="histogram",
        unit="Cycle",
        dims={"kind": str.lower},
    ),
    # DAG descriptors the Gather Unit extracted, by carrier (request,
    # notification, postEvict), on its Cache_Controller.
    gx.StatSpec(
        "hovDAGsByCarrier", kind="vector", unit="Count", element_dim="carrier"
    ),
    # In-line speculation at the Gather Unit (gem5 2026-10-15, stage 2),
    # on its Cache_Controller: entries made, leaders by mode, speculated
    # IDRs sent and dropped (unmapped, coalesced), real DAGs dropped as
    # covered, cover rows replaced, writes demoted, entries coalesced.
    *[
        gx.StatSpec(name, kind="scalar", unit="Count")
        for name in [
            "hovSpecEntries",
            "hovSpecLinesForward",
            "hovSpecLinesLine",
            "hovSpecIdrsSent",
            "hovDagsCoveredAtGU",
            "hovCoverReplaced",
            "hovSpecWritesDemoted",
            "hovSpecCoalesced",
        ]
    ],
    gx.StatSpec(
        "hovSpecIdrsDropped", kind="vector", unit="Count",
        element_dim="reason"
    ),
    # Sequencer-side suppression (stage 3): DAGs not sent because a cover
    # row held them (aliased onto a line in flight, notify), dropped from
    # a drain notification, and drain notifications not sent at all.
    gx.StatSpec(
        "hovDagsSuppressed", owner_class=SEQUENCER, kind="vector",
        unit="Count", element_dim="path"
    ),
    gx.StatSpec("hovDagsPrunedAtDrain", owner_class=SEQUENCER,
                kind="scalar", unit="Count"),
    gx.StatSpec("hovNotifsElided", owner_class=SEQUENCER, kind="scalar",
                unit="Count"),
    gx.StatSpec("hovLdindUnmatched", owner_class=SEQUENCER, kind="scalar"),
    gx.StatSpec("hovLdindStale", owner_class=SEQUENCER, kind="scalar"),
    # Functional checks of hov values (sgo mods check_hov_values,
    # sample_hov_values): all zero when the checks are off.
    *[
        gx.StatSpec(name, owner_class=SEQUENCER, kind="scalar", unit="Count")
        for name in [
            "hovValueChecks",
            "hovValueMismatches",
            "hovIndexChecks",
            "hovIndexMismatches",
            "hovChecksUnchecked",
        ]
    ],
]

# Committed loads and stores per access name (the core's commit stats,
# gem5 build v2): the insights labels in ref, the arrays' names on hov
# uops, so the same anchor array measures work done in both variants.
COMMITTED_PER_NAME = gx.StatSpec(
    re.compile(
        r"commitStats(?P<thread>\d+)\."
        r"(?P<stat>committedLoads|committedStores)\.(?P<accessor>.+)"
    ),
    name="{stat}",
    kind="scalar",
    unit="Count",
    dims={"thread": int},
    doc="Committed labelled loads or stores per access name",
)

# Per access name, since gem5 build v2: hits, misses and allocated bytes
# of every CacheMemory (`other` is an unlabelled access). hov accesses
# carry the arrays' names when the restore registered the manifest's
# `hov_entries` with the cores, else hov<p>_index and hov<p>_data.
# demand* excludes hov accesses: index* counts index accesses (uop0),
# idr* the IDRs, gather* the Gather Unit's lookups of a notification's
# index line (a miss fetches the line).
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
        ("indexHits", "Count", "Index access (uop0) hits per access name"),
        ("indexMisses", "Count",
         "Index access (uop0) misses per access name"),
        ("idrHits", "Count", "IDR hits per access name"),
        ("idrMisses", "Count", "IDR misses per access name"),
        ("idrSpecHits", "Count",
         "Speculated IDR hits per access name (also in idrHits)"),
        ("idrSpecMisses", "Count",
         "Speculated IDR misses per access name (also in idrMisses)"),
        ("gatherHits", "Count",
         "Gather Unit index line lookups with the data here"),
        ("gatherMisses", "Count",
         "Gather Unit index line lookups that fetched the line"),
        ("bytesAllocated", "Byte",
         "Bytes of blocks allocated (brought in and kept) per access name"),
    ]
]

# Snoops reaching a core's topmost copy of a line (gem5 2026-10-15), per
# access name: false sharing when the copy never used the bytes the
# requester accesses, true sharing when it did, or no requester (a
# prefetch, a back-invalidate); shared snoops let the requester read,
# unique ones take the line away.
SNOOP_SHARING = gx.StatSpec(
    re.compile(
        r"snoop(?P<sharing>FalseSharing|TrueSharing|NoRequester)"
        r"(?P<snoop>Shared|Unique)\.(?P<accessor>.+)"
    ),
    name="snoopSharing",
    owner_class=CACHE,
    kind="scalar",
    unit="Count",
    dims={
        "sharing": lambda s: {"FalseSharing": "false", "TrueSharing": "true",
                              "NoRequester": "none"}[s],
        "snoop": str.lower,
    },
    doc="Snoops at a core's topmost copy, by sharing and snoop kind",
)

# Lifetime usefulness (gem5 2026-10-15): a set that travels with a line's
# data across caches and cores, sampled when the line leaves the chip (at
# the home whose downstream is memory) or, for lines still on chip at the
# dump, once per line over the union of every copy (prefix `resident`).
# `when` is `left` or `resident`.
def _lifetime_spec(token: str, name: str, kind, doc: str) -> gx.StatSpec:
    return gx.StatSpec(
        re.compile(
            r"(?P<when>resident|)" + token + r"\.(?P<accessor>.+)"
        ),
        name=name,
        owner_class=CACHE,
        kind=kind,
        unit="Byte" if kind is UsefulBytes else "Count",
        reduce="merge",
        dims={"when": lambda s: s or "left"},
        doc=doc,
    )


LIFETIME = [
    _lifetime_spec(
        "[Ll]ifetimeUsefulBytes", "lifetimeUsefulBytes", UsefulBytes,
        "Bytes any core used of a line over its time on chip"),
    _lifetime_spec(
        "[Cc]rossCoreUsefulBytes", "crossCoreUsefulBytes", UsefulBytes,
        "Bytes only cores other than the line's first user used"),
    _lifetime_spec(
        "[Ll]ifetimeShared", "lifetimeShared", "histogram",
        "1 if a core other than the line's first user used the line"),
]

# IMP's own counters (gem5 WP3, 2026-10-25), printed as
# <prefetcher>.imp.<stat> on each IndirectMemoryPrefetcher (a child of the
# L1D's MultiPrefetcher in the imp_v4 bundles); the prefetcher's own
# pfIssued and pfUseful (Base) count IMP's prefetches alone there, since
# its stream part is off. pfTranslationFailed is Queued's (nozero).
IMP_PREFETCHER = "gem5::prefetch::IndirectMemory"
IMP = [
    *[
        gx.StatSpec(
            f"imp.{name}", owner_class=IMP_PREFETCHER, kind="scalar",
            unit="Count", doc=doc,
        )
        for name, doc in [
            ("indexReads", "PT hits whose value could be read as an index"),
            ("indexReadsEnabled",
             "Index reads of an enabled pattern above the threshold "
             "(the triggers)"),
            ("ipdAllocs", "IPD entries allocated"),
            ("ipdReleases",
             "IPD entries released after a third index without a match"),
            ("ipdStolen",
             "IPD entries whose miss tracking another entry took over"),
            ("patternsDisabled",
             "Confidence falling to the threshold from above"),
            ("patternsReplaced", "PT entries with an enabled pattern replaced"),
            ("confidenceHits",
             "Accesses matching the target of an index in the confidence "
             "window"),
            ("indirectCandidates",
             "Indirect target addresses handed to the queue"),
            ("indirectAbsentIndexLine",
             "Frontier walks stopped at an index line not in the cache"),
            ("indirectPageStop",
             "Frontier walks stopped at the end of the trigger's page"),
            ("frontierResets",
             "Frontier restarts because the index stream jumped"),
            ("streamCandidates", "Candidates of IMP's own stream part"),
            ("pendingTranslations",
             "Prefetches waiting for a translation at the dump"),
        ]
    ],
    gx.StatSpec(
        "imp.patternsEnabled", owner_class=IMP_PREFETCHER, kind="vector",
        unit="Count", element_dim="shift",
        doc="Patterns found, per shift value (shift2, ..., shiftNeg3)",
    ),
    gx.StatSpec(
        "imp.indirectDistance", owner_class=IMP_PREFETCHER,
        kind="histogram", unit="Count",
        doc="Distance in index elements of every indirect candidate",
    ),
    gx.StatSpec(
        "pfTranslationFailed", owner_class="gem5::prefetch::*",
        kind="scalar", unit="Count",
        doc="Prefetches dropped because their translation faulted",
    ),
]

SIFT_SPECS = [
    *IMP,
    USEFUL_BYTES,
    *LIFETIME,
    BYTES_TRANSFERRED,
    BYTES_TRANSFERRED_OLD,
    IND_REL_LATENCY,
    *HOV,
    *PER_NAME,
    SNOOP_SHARING,
    COMMITTED_PER_NAME,
]
