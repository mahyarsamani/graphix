from functools import reduce
from math import sqrt
from matplotlib import pyplot as plt
from matplotlib.patches import Patch
from numpy import atleast_1d
from typing import Any, List, Optional, Union
from warnings import warn

from .base_types import Node
from .compare_util import SmallestThing
from .markers import get_color_from_id, get_hatch_from_id
from .stats import Scalar
from .util import map_values_to_id


# TODO: Think about handling common parents, should it just be a string that
# represents the path to the parent (i.e. should we track common parent paths)?


def _get_common_parents(stats: List[Scalar]) -> set[Node]:
    common_parents = reduce(
        lambda x, y: x & y, (set(stat.parents()) for stat in stats)
    )
    return common_parents


def _build_discriminator_mapping(
    indices: List[dict],
    common_parents: set[Node],
    to_figure_out: List[str],
    discriminator_mapping: Optional[dict[str, str]] = None,
) -> dict[str, dict[str, int]]:
    def _get_unique_values(indices: List[dict]) -> dict[str, List[Any]]:
        unique_values = dict()
        for index in indices:
            for key, value in index.items():
                if key not in unique_values:
                    unique_values[key] = set()
                unique_values[key].add(value)
        return {key: list(value) for key, value in unique_values.items()}

    def _figure_out_mapping(
        to_figure_out: List[str],
        indices: List[dict],
    ) -> dict[str, str]:
        ret = dict()

        unique_values = _get_unique_values(indices)
        marker_count = [
            (marker, len(uniques)) for marker, uniques in unique_values.items()
        ]
        marker_count.sort(key=lambda x: x[1], reverse=True)
        markers, _ = zip(*marker_count)

        if len(markers) > len(to_figure_out):
            raise ValueError(
                f"This package only supports up to {len(to_figure_out)} markers."
            )

        for index, marker in enumerate(markers):
            ret[to_figure_out[index]] = marker
        return ret

    num_common_parents = len(common_parents)
    if num_common_parents == 0:
        raise RuntimeError("No common parents found in the provided stats.")

    if not all(index.keys() == indices[0].keys() for index in indices):
        raise ValueError("All stats should have the same index keys.")
    the_indices = indices[0].keys()

    mapping = dict()
    use_parent_as = None
    copy_to_figure_out = ["subgroup", "group", "hue", "hatch", "subplot"]
    if discriminator_mapping is None:
        warn(
            "`discriminator_mapping` not provided. Figuring out automatically."
        )
        if num_common_parents > 1:
            warn(
                "Provided stats have more than one common parent. "
                "Using `subgroup` to demonstrate parents."
            )
            use_parent_as = "subgroup"
            copy_to_figure_out.remove("subgroup")
        mapping = _figure_out_mapping(
            to_figure_out=copy_to_figure_out,
            indices=indices,
        )
        mapping[use_parent_as] = "parent"
        warn(f"Automatically figured out mapping: {mapping}")
    else:
        # NOTE: Catch if the user has specified the same
        # value for two different keys
        if len(set(discriminator_mapping.values())) != len(
            list(discriminator_mapping.values())
        ):
            raise ValueError(
                "Provided values in `marker_mapping` should be "
                f"unique and should be from {to_figure_out}."
            )
        # NOTE: values specified should be in to_figure_out
        if not set(discriminator_mapping.values()) <= set(to_figure_out):
            raise ValueError(
                "Provided values in `marker_mapping` should be in "
                f"{to_figure_out}."
            )
        use_parent_as = discriminator_mapping.get("parent", None)
        if use_parent_as is None and num_common_parents > 1:
            raise ValueError(
                "Provided stats have more than one common parent. "
                "No instruction provided for `parent`. "
            )
        if use_parent_as is not None and num_common_parents == 1:
            warn(
                "Provided stats have only one common parent. "
                "Instruction provided for `parent`."
            )
        copy_mapping = discriminator_mapping.copy()
        copy_mapping.pop("parent", None)
        if set(copy_mapping.keys()) != set(the_indices):
            raise ValueError(
                "With the exception of `parent`, "
                "provided keys in `marker_mapping` should exhaustively cover "
                "the keys in the index of the stats."
            )
        for key, value in copy_mapping.items():
            if value not in to_figure_out:
                raise ValueError(
                    "Provided values in `marker_mapping` should be in "
                    f"{to_figure_out}."
                )
            mapping[value] = key
        mapping[use_parent_as] = "parent"

    unique_values = _get_unique_values(indices)
    unique_values["parent"] = list(common_parents)

    discriminator_map_map = dict()
    num_unique_values = dict()
    for key in to_figure_out:
        temp = mapping.get(key, None)
        if temp is not None:
            discriminator_map_map[key] = map_values_to_id(
                unique_values.get(temp, [])
            )
        num_unique_values[key] = (
            len(unique_values.get(temp, [])) if temp else 1
        )

    return [
        mapping,
        discriminator_map_map,
        num_unique_values,
    ]


def _draw_spanning_line(
    ax: plt.axes,
    xmin: Union[int, float],
    xmax: Union[int, float],
    y: Union[int, float],
    text: str,
    color: str,
    end_tick_height_multiplier: float,
) -> None:
    ax.hlines(y=y, xmin=xmin, xmax=xmax, color=color)
    ax.plot(
        [xmin, xmin],
        [y * end_tick_height_multiplier, y],
        color=color,
    )
    ax.annotate(
        text,
        xy=((xmin + xmax) / 2, y),
        ha="center",
        va="bottom",
        color=color,
    )


def plot_bar(
    stats: List[Scalar],
    discriminator_mapping: Optional[dict[str, str]] = None,
    nrows: Optional[int] = None,
    ncols: Optional[int] = None,
    sharex: Optional[bool] = False,
    sharey: Optional[bool] = False,
    figsize: Optional[tuple[int, int]] = (14, 8.32),
    hatch_density: Optional[int] = 3,
    hatch_color: Optional[str] = "black",
    bar_width: int = 1,
    subgroup_gap: int = 1,
    group_gap: int = 4,
    annotation_color: str = "black",
    end_tick_height_multiplier: float = 0.9875,
    subgroup_id_height_multiplier: float = 1.0375,
    group_id_height_multiplier: float = 1.075,
    **kwargs,
) -> tuple[plt.figure, List[plt.axes]]:
    # NOTE: Discriminators for distinguishing different values
    to_figure_out = ["hue", "subgroup", "group", "hatch", "subplot"]
    common_parents = _get_common_parents(stats)
    num_common_parents = len(common_parents)
    if num_common_parents == 0:
        raise ValueError("No common parents found in the provided stats.")
    (
        mapping,
        discriminator_map_map,
        num_unique_values,
    ) = _build_discriminator_mapping(
        [stat.index() for stat in stats],
        common_parents,
        to_figure_out,
        discriminator_mapping,
    )

    def _get_good_dimensions(one_d: int) -> tuple[int, int]:
        side = int(sqrt(one_d))
        while one_d % side != 0:
            side -= 1
        return max(side, one_d // side), min(side, one_d // side)

    if nrows is not None and ncols is not None:
        if nrows * ncols != num_unique_values["subplot"]:
            raise ValueError(
                "Provided nrows and ncols should multiply to number of unique "
                f"values for marker_mapping['subplot'] ({mapping['subplot']}) "
                f"which is {num_unique_values['subplot']}."
            )
    elif (nrows is not None) != (ncols is not None):
        raise ValueError(
            "If one of nrows or ncols is provided, both should be provided."
        )
    else:
        nrows, ncols = _get_good_dimensions(num_unique_values["subplot"])

    if nrows is None or ncols is None:
        raise RuntimeError("Something went wrong with the dimensions.")

    if sharex and nrows == 1:
        warn(f"`sharex` set to True when there is one row.")
    if sharey and ncols == 1:
        warn(f"`sharey` set to True when there is one column.")

    subgroup_width = (
        num_unique_values["hue"] * num_unique_values["hatch"] * bar_width
    )
    group_width = (
        num_unique_values["subgroup"] * subgroup_width
        + (num_unique_values["subgroup"] - 1) * subgroup_gap
    )
    global_offset = subgroup_gap
    group_offset_multiplier = group_width + group_gap
    subgroup_offset_multiplier = subgroup_width + subgroup_gap
    hatch_offset_multiplier = num_unique_values["hue"] * bar_width

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        sharex=sharex,
        sharey=sharey,
        figsize=figsize,
        **kwargs,
    )

    axes = atleast_1d(axes)
    axes = axes.flatten()

    def _get_discriminator_value(
        discriminator: str, mapping: dict, index: dict, parent: Node
    ):
        tie = mapping.get(discriminator, None)
        if tie == "parent":
            return parent
        elif tie is not None:
            return index[mapping[discriminator]]
        else:
            return None

    def _get_id_for(
        discriminator: str,
        index: dict,
        parent: Node,
        mapping,
        discriminator_map_map,
    ):
        discriminator_value = _get_discriminator_value(
            discriminator, mapping, index, parent
        )
        if discriminator_value is not None:
            return discriminator_map_map[discriminator][discriminator_value]
        else:
            return 0

    max_height = dict()
    for stat in stats:
        index = stat.index()
        parents = stat.parents()
        for parent in parents:
            if parent not in common_parents:
                continue
            hue_id = _get_id_for(
                "hue", index, parent, mapping, discriminator_map_map
            )
            color = get_color_from_id(hue_id)
            hatch_id = _get_id_for(
                "hatch", index, parent, mapping, discriminator_map_map
            )
            pattern = get_hatch_from_id(hatch_id)
            group_id = _get_id_for(
                "group", index, parent, mapping, discriminator_map_map
            )
            subgroup_id = _get_id_for(
                "subgroup", index, parent, mapping, discriminator_map_map
            )
            subplot_id = _get_id_for(
                "subplot", index, parent, mapping, discriminator_map_map
            )
            height = stat.value()[parent]
            x = (
                global_offset
                + group_id * group_offset_multiplier
                + subgroup_id * subgroup_offset_multiplier
                + hatch_id * hatch_offset_multiplier
                + hue_id * bar_width
            )

            axes[subplot_id].bar(
                x=x,
                height=height,
                width=bar_width,
                color=color,
                hatch=pattern * hatch_density,
                edgecolor=hatch_color,
            )

            if subplot_id not in max_height:
                max_height[subplot_id] = dict()
            if group_id not in max_height[subplot_id]:
                max_height[subplot_id][group_id] = dict()
                max_height[subplot_id][group_id][
                    "max_height"
                ] = SmallestThing()
            if subgroup_id not in max_height[subplot_id][group_id]:
                max_height[subplot_id][group_id][subgroup_id] = SmallestThing()
            max_height[subplot_id][group_id][subgroup_id] = max(
                height, max_height[subplot_id][group_id][subgroup_id]
            )
            max_height[subplot_id][group_id]["max_height"] = max(
                max_height[subplot_id][group_id]["max_height"],
                max_height[subplot_id][group_id][subgroup_id],
            )

    def _get_value_for(
        discriminator: str, discriminator_map_map: dict, id
    ) -> str:
        for key, value in discriminator_map_map[discriminator].items():
            if value == id:
                return key

    hue_patches = [
        Patch(
            facecolor=get_color_from_id(i),
            hatch="",
            label=f"{mapping['hue']}: {_get_value_for('hue', discriminator_map_map, i)}",
        )
        for i in range(num_unique_values["hue"])
    ]
    hatch_patches = [
        Patch(
            facecolor="white",
            hatch=get_hatch_from_id(i) * (hatch_density + 1),
            label=f"{mapping['hatch']}: {_get_value_for('hatch', discriminator_map_map, i)}",
            edgecolor=hatch_color,
        )
        for i in range(num_unique_values["hatch"])
    ]
    handles = hue_patches + hatch_patches
    for subplot_id, ax in enumerate(axes):
        # FIXME: what if there are not more than one subplot?
        ax.title.set_text(
            f"{mapping['subplot']}: {_get_value_for('subplot', discriminator_map_map, subplot_id)}"
        )
        for group_id in range(num_unique_values["group"]):
            for subgroup_id in range(num_unique_values["subgroup"]):
                tall_bar = (
                    max_height[subplot_id][group_id][subgroup_id]
                    * subgroup_id_height_multiplier
                )
                left = (
                    global_offset
                    + group_id * group_offset_multiplier
                    + subgroup_id * subgroup_offset_multiplier
                    - (bar_width / 2)
                )
                right = left + subgroup_width
                _draw_spanning_line(
                    ax,
                    left,
                    right,
                    tall_bar,
                    f"{mapping['subgroup']}: {_get_value_for('subgroup', discriminator_map_map, subgroup_id)}",
                    annotation_color,
                    end_tick_height_multiplier,
                )
            tall_bar = (
                max_height[subplot_id][group_id]["max_height"]
                * group_id_height_multiplier
            )
            left = (
                global_offset
                + group_id * group_offset_multiplier
                - (bar_width / 2)
            )
            right = left + group_width
            _draw_spanning_line(
                ax,
                left,
                right,
                tall_bar,
                f"{mapping['group']}: {_get_value_for('group', discriminator_map_map, group_id)}",
                annotation_color,
                end_tick_height_multiplier,
            )
        ax.legend(handles=handles)

    return fig, axes
