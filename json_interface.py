from typing import List
from warnings import warn

from .base_types import Node
from .stats import Distribution, Scalar


def compile_json_stats(
    index: dict, to_compile: dict, current_build: dict, root: Node
) -> dict:
    for key, value in to_compile.items():
        # ignore hierarchical stats like vectors
        if "." in key:
            continue
        if isinstance(value, dict):
            if value.get("type", "otherwise") == "SimObject":
                node = Node(
                    value["name"], ".".join([root.path(), value["name"]])
                )
                root.add_child(node)
                compile_json_stats(index, value, current_build, node)
            elif value.get("type", "otherwise") == "SimObjectVector":
                for item in value["value"]:
                    node = Node(
                        item["name"], ".".join([root.path(), item["name"]])
                    )
                    root.add_child(node)
                    compile_json_stats(index, item, current_build, node)
            elif value.get("type", "otherwise") == "Scalar":
                if key not in current_build:
                    current_build[key] = Scalar(index, key)
                current_build[key].process_dict(root, key, value)
            elif value.get("type", "otherwise") == "Distribution":
                if key not in current_build:
                    current_build[key] = Distribution(index, key)
                current_build[key].process_dict(root, key, value)
            else:
                warn(
                    f"Skipping {key} with type {value.get('type', 'otherwise')}"
                )
    return current_build


def create_graph_format(root: Node) -> None:
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
