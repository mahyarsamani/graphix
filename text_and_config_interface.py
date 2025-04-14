import subprocess

from pathlib import Path
from warnings import warn

from .base_types import Node
from .stats import find_matching_stat_class_from_line_wo_parent_path


def parse_config_json(root: Node, config_json: dict) -> None:
    def _is_sim_object(value):
        return isinstance(value, dict) and (
            "type" in value
            and "cxx_class" in value
            and "name" in value
            and "path" in value
        )

    def _is_sim_object_vector(value):
        return isinstance(value, list) and all(
            _is_sim_object(item) for item in value
        )

    for key, value in config_json.items():
        if _is_sim_object(value):
            assert key == value["name"], f"key: {key}, value: {value}"
            # NOTE: This is because path for original root is ""
            path = ".".join(filter(None, [root.path(), key]))
            assert path == value["path"], f"path: {path}, value: {value}"
            node = Node(key, path)
            root.add_child(node)
            parse_config_json(node, value)
        if _is_sim_object_vector(value):
            for item in value:
                name = item["name"]
                path = ".".join([root.path(), name])
                assert path == item["path"], f"path: {path}, item: {item}"
                node = Node(name, path)
                root.add_child(node)
                parse_config_json(node, item)


def parse_stats_txt(
    index: dict, root: Node, stats_txt_path: Path, dump_version_to_proces: int
) -> None:
    def _find_string_locations(file_path: Path, search_string: str):
        result = subprocess.run(
            ["grep", "-n", search_string, str(file_path)],
            capture_output=True,
            text=True,
        )
        line_numbers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                line_numbers.append(int(line.split(":", 1)[0]))
        return line_numbers

    begin_locations = _find_string_locations(
        stats_txt_path, "Begin Simulation Statistics"
    )
    end_locations = _find_string_locations(
        stats_txt_path, "End Simulation Statistics"
    )
    if len(begin_locations) != len(end_locations):
        raise RuntimeError(
            f"Number of begin and end locations do not match: {begin_locations}, {end_locations}"
        )

    # NOTE: Author is quircky and does not like treating things that are logically
    # equal differently. So I average them into a new variable num_dumps_found.
    num_dumps_found = (len(begin_locations) + len(end_locations)) // 2
    if dump_version_to_proces >= num_dumps_found:
        raise ValueError(
            f"Dump version {dump_version_to_proces} is bigger than the total number of dumps {num_dumps_found}."
        )

    # NOTE: Since these line numbers are returned by grep (i.e. the numbers
    # start from 1 instead of 0), we need to subtract 1 to convert them to
    # 0-based. However, since we don't want to process the Begin and End lines,
    # we don't need to add 1 to the start and since slice operator is exclusive
    # of the end index, we don't need to subtract 1 from the end.
    start_index = begin_locations[dump_version_to_proces]
    end_index = end_locations[dump_version_to_proces]
    ret = dict()
    with open(stats_txt_path, "r") as stats_txt_file:
        lines = stats_txt_file.readlines()[start_index:end_index]
    for line in lines:
        if not line.strip():
            continue
        rstripped_line = line.rstrip()
        first_column_tokens = rstripped_line.split()[0].split(".")
        parent = root.get_maximal_match_descendent_from_tokenized_first_column(
            first_column_tokens
        )
        line_wo_parent_path = rstripped_line.removeprefix(parent.path() + ".")

        matching_stat_class = (
            find_matching_stat_class_from_line_wo_parent_path(
                line_wo_parent_path
            )
        )
        if matching_stat_class is None:
            warn(
                f"Skipping stat line {line} since it does not match any stat class."
            )
            continue
        stat_name = matching_stat_class.get_stat_name_from_line_wo_parent_path(
            line_wo_parent_path
        )
        if stat_name not in ret:
            ret[stat_name] = matching_stat_class(index, stat_name)
        ret[stat_name].process_line(parent, line_wo_parent_path)
    return ret
