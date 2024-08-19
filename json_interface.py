from typing import List

from .base_types import GroupNode
from .stats import Distribution, Scalar


def traverse_stats(stat: dict, stats: dict, root: GroupNode) -> None:
    for key, value in stat.items():
        # ignore hierarchical stats like vectors
        if "." in key:
            continue
        if type(value) == dict:
            if value.get("type", "otherwise") == "Group":
                node = GroupNode(key, ".".join([root.path(), key]))
                root.add_child(node)
                traverse_stats(value, stats, node)
            if value.get("type", "otherwise") == "Scalar":
                if key not in stats:
                    stats[key] = Scalar({}, key)
                stats[key].process_dict(root, key, value)
            if value.get("type", "otherwise") == "Distribution":
                if key not in stats:
                    stats[key] = Distribution({}, key)
                stats[key].process_dict(root, key, value)
    return stats


def create_graph_format(root: GroupNode) -> None:
    v_ret = []
    e_ret = []
    v_ret.append(root.id())
    for child in root.children():
        e_ret.append((root.id(), child.id()))
    for child in root.children():
        v_from_child, e_from_child = create_graph_format(child)
        v_ret += v_from_child
        e_ret += e_from_child
    return v_ret, e_ret
