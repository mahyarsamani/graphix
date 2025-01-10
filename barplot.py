from math import sqrt
from matplotlib import pyplot as plt
from matplotlib.legend_handler import HandlerTuple
from matplotlib.patches import Patch
from numpy import atleast_1d
from typing import Any, List, Optional, Union
from warnings import warn

from .base_types import Node
from .compare_util import SmallestThing
from .markers import get_color_from_id, get_hatch_from_id
from .stats import Scalar
from .util import _get_common_parents, DiscriminatorMap

# TODO: Think about handling common parents, should it just be a string that
# represents the path to the parent (i.e. should we track common parent paths)?


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
    custom_order: Optional[dict[str, List[Any]]] = None,
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
    group_id_subgroup_id_height_difference: float = 0.05,
    **kwargs,
) -> tuple[plt.figure, List[plt.axes]]:
    # NOTE: Discriminators for distinguishing different values
    all_discriminators = ["hue", "subgroup", "group", "hatch", "subplot"]
    common_parents = _get_common_parents(stats)
    num_common_parents = len(common_parents)
    if num_common_parents == 0:
        raise ValueError("No common parents found in the provided stats.")
    discriminator_map = DiscriminatorMap(
        all_discriminators, discriminator_mapping, custom_order
    )
    discriminator_map.build(stats, common_parents)

    def _get_good_dimensions(one_d: int) -> tuple[int, int]:
        side = int(sqrt(one_d))
        while one_d % side != 0:
            side -= 1
        return max(side, one_d // side), min(side, one_d // side)

    if nrows is not None and ncols is not None:
        if nrows * ncols != discriminator_map.get_num_unique_values("subplot"):
            raise ValueError(
                "Provided nrows and ncols should multiply to number of unique "
                f"values for discriminator_mapping['subplot'] "
                f"({discriminator_map.get_index_for('subplot')})."
                f"which is {discriminator_map.get_num_unique_values('subplot')}."
            )
    elif (nrows is not None) != (ncols is not None):
        raise ValueError(
            "If one of nrows or ncols is provided, both should be provided."
        )
    else:
        nrows, ncols = _get_good_dimensions(
            discriminator_map.get_num_unique_values("subplot")
        )

    if nrows is None or ncols is None:
        raise RuntimeError("Something went wrong with the dimensions.")

    if sharex and nrows == 1:
        warn(f"`sharex` set to True when there is one row.")
    if sharey and ncols == 1:
        warn(f"`sharey` set to True when there is one column.")

    subgroup_width = (
        discriminator_map.get_num_unique_values("hue")
        * discriminator_map.get_num_unique_values("hatch")
        * bar_width
    )
    group_width = (
        discriminator_map.get_num_unique_values("subgroup") * subgroup_width
        + (discriminator_map.get_num_unique_values("subgroup") - 1)
        * subgroup_gap
    )
    global_offset = subgroup_gap
    group_offset_multiplier = group_width + group_gap
    subgroup_offset_multiplier = subgroup_width + subgroup_gap
    hatch_offset_multiplier = (
        discriminator_map.get_num_unique_values("hue") * bar_width
    )

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

    max_height = dict()
    for stat in stats:
        index = stat.index()
        parents = stat.parents()
        for parent in parents:
            if parent not in common_parents:
                continue
            hue_id = discriminator_map.get_id_for(
                "hue",
                index,
                parent,
            )
            color = get_color_from_id(hue_id)
            hatch_id = discriminator_map.get_id_for("hatch", index, parent)
            pattern = get_hatch_from_id(hatch_id)
            group_id = discriminator_map.get_id_for("group", index, parent)
            subgroup_id = discriminator_map.get_id_for(
                "subgroup",
                index,
                parent,
            )
            subplot_id = discriminator_map.get_id_for("subplot", index, parent)
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

    handles = []
    if discriminator_map.mapped("hue"):
        handles += [
            Patch(
                facecolor=get_color_from_id(i),
                hatch="",
                label=f"{discriminator_map.get_index_for('hue')}: {discriminator_map.get_value_for('hue', i)}",
            )
            for i in range(discriminator_map.get_num_unique_values("hue"))
        ]
    if discriminator_map.mapped("hatch"):
        handles += [
            Patch(
                facecolor="white",
                hatch=get_hatch_from_id(i) * (hatch_density + 1),
                label=f"{discriminator_map.get_index_for('hatch')}: {discriminator_map.get_value_for('hatch', i)}",
                edgecolor=hatch_color,
            )
            for i in range(discriminator_map.get_num_unique_values("hatch"))
        ]

    for subplot_id, ax in enumerate(axes):
        for group_id in range(
            discriminator_map.get_num_unique_values("group")
        ):
            for subgroup_id in range(
                discriminator_map.get_num_unique_values("subgroup")
            ):
                if discriminator_map.mapped("subgroup"):
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
                        f"{discriminator_map.get_index_for('subgroup')}: {discriminator_map.get_value_for('subgroup', subgroup_id)}",
                        annotation_color,
                        end_tick_height_multiplier,
                    )
            if discriminator_map.mapped("group"):
                tall_bar = (
                    max_height[subplot_id][group_id]["max_height"]
                    * subgroup_id_height_multiplier
                    + group_id_subgroup_id_height_difference
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
                    f"{discriminator_map.get_index_for('group')}: {discriminator_map.get_value_for('group', group_id)}",
                    annotation_color,
                    end_tick_height_multiplier,
                )
        if discriminator_map.mapped("subplot"):
            ax.title.set_text(
                f"{discriminator_map.get_index_for('subplot')}: {discriminator_map.get_value_for('subplot', subplot_id)}",
            )
        ax.legend(handles=handles)
        ax.set_xticks([])
        ax.set_xticklabels([])

    return (
        fig,
        axes,
    )


def plot_stacked_bar(stats: List[List[Scalar]]):
    pass
