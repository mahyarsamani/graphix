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

# ---------------------------------------------------------------------------
# Wave 1 (SIFT post-QE plan, 2026-10-25): one list per work package, filled
# from the stats each package's PLAN.md announces
# (projects/sift/docs/agents/<date>-wp<N>/PLAN.md on branch agent/wp<N>).
# A list stays empty, with a TODO naming the stats the package's source
# report expects, until the package fixes the printed names; each package
# adds its specs in the same change as its stats (wave1-common.md).

# WP4 (evaluation infrastructure: controls, the memory window M0, the MMU
# on prefetchers) adds no gem5 stat. M0 reads stock DRAM stats, which
# graphix's built-in specs already cover (checked with runs.catalog() on
# the WP4 smokes, 2026-10-25): readRowHits, readBursts and
# bytesPerActivate on gem5::memory::DRAMInterface; readReqs, readBursts,
# avgRdQLen, rdQLenPdf, numRdRetry and rdPerTurnAround on
# gem5::memory::MemCtrl. readBursts exists on both classes, so pick one
# with get("readBursts", owner_class=...). busUtilRead and readRowHitRate
# are Formulas, which graphix skips: compute them from their components.
WP4_SPECS: list = []

# WP0 (the target flow, 3a/3b), from WP0's PLAN.md section 6 (agent/wp0,
# commit 70ab712, 2026-10-25; names marked "proposed" there, so check them
# against the merged code): on the Gather Unit's and the Indirect Unit's
# Cache_Controller. idrHits and idrMisses (PER_NAME) move to the Gather
# Unit and count injected requests; SendIDR and HovAck go away.
WP0_SPECS = [
    gx.StatSpec("hovFwd", kind="vector", unit="Count", element_dim="outcome",
                doc="Gather Unit requests injected for the Indirect Unit: "
                "issued, skippedHeld, completed, declined, droppedNoTarget"),
    gx.StatSpec("hovFwdLatency", kind="histogram", unit="Cycle",
                plots=("cdf", "box"),
                doc="Injection to the Indirect Unit's CompAck"),
    gx.StatSpec("hovExpectSent", kind="scalar", unit="Count",
                doc="Expect notices attached to index data"),
    gx.StatSpec("hovDupDropped", kind="scalar", unit="Count",
                doc="Core requests dropped because a delivery served them"),
    gx.StatSpec("hovExpect", kind="vector", unit="Count", element_dim="outcome",
                doc="Expect notices at the Indirect Unit: allocated, present, "
                "droppedNoTBE, afterData, busy, timedOut"),
    gx.StatSpec("hovDeliver", kind="vector", unit="Count", element_dim="outcome",
                doc="Deliveries at the Indirect Unit: intoExpect, onArrival, "
                "absorbed, declined"),
]

# WP2 (run-ahead gate and drop-on-full), from WP2's PLAN.md section 4.5
# (agent/wp2, commit fecc292, 2026-10-25); all nozero, on the Gather
# Unit's or the Indirect Unit's Cache_Controller. hovSpecIdrsDropped (in
# HOV above) gains the element `full`; the vector spec reads it unchanged.
# The per-pair vectors have one element per side-car pair entry (32).
WP2_SPECS = [
    *[
        gx.StatSpec(name, kind="scalar", unit="Count", doc=doc)
        for name, doc in [
            ("hovSpecIdrsDroppedAtIU",
             "Run-ahead IDRs the Indirect Unit answered with HovAck for "
             "want of a TBE (dropped, not retried)"),
            ("hovSpecIdrsRetriedAtIU",
             "Run-ahead IDRs the Indirect Unit sent a RetryAck (0 with "
             "drop-on-full)"),
            ("hovRaRowsAllocated", "Stream rows allocated"),
            ("hovRaRowsReplaced", "Stream rows replaced (LRU)"),
            ("hovRaRebases", "Stream rows re-based on a jump of the index"),
        ]
    ],
    *[
        gx.StatSpec(name, kind="vector", unit="Count", element_dim="pair",
                    doc=doc)
        for name, doc in [
            ("hovRaDemands", "Real DAGs seen per pair entry"),
            ("hovRaIssued", "Run-ahead IDRs issued per pair entry"),
            ("hovRaHits", "Run-ahead IDRs a real DAG used, per pair entry"),
            ("hovRaGated", "Leaders the stream row's confidence gated off"),
            ("hovRaThrottled",
             "Leaders gated off by the accuracy back-off"),
        ]
    ],
    gx.StatSpec("hovRaAccuracy", kind="histogram", unit="Percent",
                doc="Run-ahead accuracy per epoch (one sample per epoch)"),
    gx.StatSpec("hovRaDistance", kind="histogram", unit="Count",
                doc="Elements of lead of each run-ahead entry over its "
                "leader"),
]

# WP3 (IMP's own stats, spec section 5.1), from WP3's PLAN.md, W3
# (agent/wp3, commit 6f8ae45, 2026-10-25): a statistics group `imp` under
# each IndirectMemory prefetcher, printed `<prefetcher>.imp.<stat>`, plus
# Queued's `pfTranslationFailed` (nozero) on every queued prefetcher.
IMP = "gem5::prefetch::IndirectMemory"
WP3_SPECS = [
    *[
        gx.StatSpec(f"imp.{name}", owner_class=IMP, kind="scalar",
                    unit="Count", doc=doc)
        for name, doc in [
            ("indexReads", "PT hits with a readable index value"),
            ("indexReadsEnabled",
             "Index reads on an enabled pattern above threshold (triggers)"),
            ("ipdAllocs", "IPD entries allocated"),
            ("ipdReleases", "IPD entries released without a match"),
            ("ipdStolen", "IPD entries another PT entry took over"),
            ("patternsDisabled", "Patterns whose confidence fell to the "
             "threshold"),
            ("patternsReplaced", "PT entries with an enabled pattern "
             "evicted"),
            ("confidenceHits", "Accesses matching an enabled pattern's "
             "target"),
            ("indirectCandidates", "Indirect targets handed to Queued"),
            ("indirectAbsentIndexLine",
             "Frontier walks stopped at an index line not in the cache"),
            ("indirectPageStop",
             "Frontier walks stopped at the end of the trigger's page"),
            ("frontierResets", "Frontier restarts on an index-stream jump"),
            ("streamCandidates", "Candidates of IMP's own stream part"),
            ("pendingTranslations",
             "Prefetches waiting for a translation at the dump"),
        ]
    ],
    gx.StatSpec("imp.patternsEnabled", owner_class=IMP, kind="vector",
                unit="Count", element_dim="shift",
                doc="Patterns found, per shift_values entry"),
    gx.StatSpec("imp.indirectDistance", owner_class=IMP, kind="histogram",
                unit="Count", plots=("cdf", "pdf"),
                doc="j - i of every indirect candidate, in elements"),
    gx.StatSpec("pfTranslationFailed", owner_class="gem5::prefetch::*",
                kind="scalar", unit="Count",
                doc="Prefetch translations that faulted (prefetch dropped)"),
]

WAVE1_SPECS = [*WP0_SPECS, *WP2_SPECS, *WP3_SPECS, *WP4_SPECS]

SIFT_SPECS = [
    USEFUL_BYTES,
    *LIFETIME,
    BYTES_TRANSFERRED,
    BYTES_TRANSFERRED_OLD,
    IND_REL_LATENCY,
    *HOV,
    *PER_NAME,
    SNOOP_SHARING,
    COMMITTED_PER_NAME,
    *WAVE1_SPECS,
]
