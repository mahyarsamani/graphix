"""graphix: typed gem5 statistics, selection, reduction, and DataFrame export.

Typical use:

    import graphix as gx

    runs = gx.RunSet.from_dirs("example_data/*/*", labels=my_labels)
    cycles = runs["numCycles"]                       # a Scalar across runs
    l1d = runs["usefulBytes"].select(owner="*.dcache.cache")
    merged = l1d.merge(over="owner")                 # one histogram per run
    merged.to_frame()                                # a pandas DataFrame

Extend it with `StatSpec`s for your own stats and an `OwnerScheme` for
canonical owner names; see `examples/sift/`.
"""

from .config import ConfigTree, SimObject
from .frame import concat, table
from .names import StatName, split_name
from .owners import OwnerScheme
from .parse import StatLine, count_dumps, dump_locations, find_dump_file, read_dump
from .records import build_blocks, suggest_specs
from .run import AmbiguousStatError, Run, RunSet
from .specs import Registry, StatSpec
from .stats import (
    Buckets,
    ControllerCount,
    Histogram,
    Index,
    Scalar,
    Stat,
    Vector,
)

__all__ = [
    "AmbiguousStatError",
    "Buckets",
    "ConfigTree",
    "ControllerCount",
    "Histogram",
    "Index",
    "OwnerScheme",
    "Registry",
    "Run",
    "RunSet",
    "Scalar",
    "SimObject",
    "Stat",
    "StatLine",
    "StatName",
    "StatSpec",
    "Vector",
    "build_blocks",
    "concat",
    "count_dumps",
    "dump_locations",
    "find_dump_file",
    "read_dump",
    "split_name",
    "suggest_specs",
    "table",
]
