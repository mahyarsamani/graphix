from functools import reduce
from typing import Any, List, Optional
from warnings import warn

from .base_types import Node, Stat
from .compare_util import BiggestThing
from .stats import Scalar


def _get_common_parents(stats: List[Scalar]) -> set[Node]:
    common_parents = reduce(
        lambda x, y: x & y, (set(stat.parents()) for stat in stats)
    )
    return common_parents


def _get_unique_values(indices: List[dict]) -> dict[str, List[Any]]:
    unique_values = dict()
    for index in indices:
        for key, value in index.items():
            if key not in unique_values:
                unique_values[key] = set()
            unique_values[key].add(value)
    return {key: list(value) for key, value in unique_values.items()}


class DiscriminatorMap:
    def __init__(
        self,
        priority_ordered_discriminators: List[str],
        discriminator_mapping: Optional[dict[str, str]],
        custom_index_order: Optional[dict[str, List[str]]],
    ) -> None:
        # NOTE: from now on, we can assume self._discriminators is a list
        # sorted based on the priority of the discriminators
        # The higher the discriminator is in the order, the more diverse
        # indices it would be assigned to. That is, in case,
        # `discriminator_mapping` is not provided.
        self._discriminators = priority_ordered_discriminators
        self._user_provided_discriminator_mapping = discriminator_mapping
        self._custom_index_order = custom_index_order

    # NOTE: This function builds the discriminator mapping which is a
    # complex dictionary that maps the name of the discriminator to
    # the index it should use to determine different values for it
    # as well as the different values of that index to an integer id and
    # a reverse mapping of that.
    def build(self, stats: List[Stat], common_parents: List[Node]) -> None:
        num_common_parents = len(common_parents)
        if num_common_parents == 0:
            raise ValueError("No common parents found in the provided stats.")

        if not all(
            stat.index().keys() == stats[0].index().keys() for stat in stats
        ):
            raise ValueError("All stats should have the same index keys.")
        the_indices = stats[0].index().keys()

        unique_values = _get_unique_values([stat.index() for stat in stats])
        unique_values["parent"] = list(common_parents)
        if self._custom_index_order is not None:
            for index, order in self._custom_index_order.items():
                if index not in unique_values:
                    raise ValueError(f"Index {index} not found in the stats.")
                order_dict = {value: rank for rank, value in enumerate(order)}
                unique_values[index] = sorted(
                    unique_values[index],
                    key=lambda x: order_dict.get(x, BiggestThing()),
                )
        temp_discriminators = self._discriminators.copy()

        partial_discriminator_index_mapping = dict()
        use_parent_as = None
        if self._user_provided_discriminator_mapping is None:
            warn(
                "`discriminator_mapping` not provided. Figuring out automatically."
            )
            if num_common_parents > 1:
                warn(
                    "Provided stats have more than one common parent. "
                    "Using `subgroup` to demonstrate parents."
                )
                use_parent_as = "subgroup"
                temp_discriminators.remove("subgroup")
            partial_discriminator_index_mapping = (
                self._figure_out_partial_discriminator_index_mapping(
                    temp_discriminators,
                    unique_values,
                )
            )
            partial_discriminator_index_mapping[use_parent_as] = "parent"
            warn(
                f"Automatically figured out mapping: {partial_discriminator_index_mapping}"
            )
        else:
            # NOTE: Catch if the user has specified the same
            # value for two different keys
            if len(
                set(self._user_provided_discriminator_mapping.values())
            ) != len(list(self._user_provided_discriminator_mapping.values())):
                raise ValueError(
                    "Provided values in `marker_mapping` should be "
                    f"unique and should be from {self._discriminators}."
                )
            # NOTE: values specified should be in to_figure_out
            if not set(
                self._user_provided_discriminator_mapping.values()
            ) <= set(self._discriminators):
                raise ValueError(
                    "Provided values in `marker_mapping` should be in "
                    f"{self._discriminators}."
                )
            use_parent_as = self._user_provided_discriminator_mapping.get(
                "parent", None
            )
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
            copy_user_provided_discriminator_mapping = (
                self._user_provided_discriminator_mapping.copy()
            )
            copy_user_provided_discriminator_mapping.pop("parent", None)
            if set(copy_user_provided_discriminator_mapping.keys()) != set(
                the_indices
            ):
                raise ValueError(
                    "With the exception of `parent`, "
                    "provided keys in `marker_mapping` should exhaustively cover "
                    "the keys in the index of the stats."
                )
            for key, value in copy_user_provided_discriminator_mapping.items():
                if value not in self._discriminators:
                    raise ValueError(
                        "Provided values in `marker_mapping` should be in "
                        f"{self._discriminators}."
                    )
                partial_discriminator_index_mapping[value] = key
            partial_discriminator_index_mapping[use_parent_as] = "parent"

        discriminator_mapping = dict()
        for key in self._discriminators:
            temp = partial_discriminator_index_mapping.get(key, None)
            if temp is not None:
                if temp not in unique_values:
                    raise RuntimeError(
                        "Values inside partial_discriminator_index_mapping "
                        "should be in unique_values."
                    )
                value_id_map = self._map_values_to_id(
                    unique_values.get(temp, [])
                )
                id_value_map = {
                    value: key for key, value in value_id_map.items()
                }
                discriminator_mapping[key] = {
                    "index": temp,
                    "num_unique_values": len(unique_values[temp]),
                    "value_id_map": value_id_map,
                    "id_value_map": id_value_map,
                }
        self._discriminator_mapping = discriminator_mapping

    def get_mapping(self):
        return self._discriminator_mapping

    def mapped(self, discriminator: str) -> bool:
        return discriminator in self._discriminator_mapping

    def get_index_for(self, discriminator: str) -> str:
        if discriminator not in self._discriminator_mapping:
            return None
        return self._discriminator_mapping[discriminator]["index"]

    def get_num_unique_values(self, discriminator: str) -> int:
        return (
            self._discriminator_mapping[discriminator]["num_unique_values"]
            if discriminator in self._discriminator_mapping
            else 1
        )

    def _get_discriminator_value(
        self, discriminator: str, index: dict, parent: Node
    ):
        if discriminator not in self._discriminator_mapping:
            return None
        tie = self._discriminator_mapping[discriminator]["index"]
        if tie == "parent":
            return parent
        else:
            return index[tie]

    def get_id_for(
        self,
        discriminator: str,
        index: dict,
        parent: Node,
    ):
        discriminator_value = self._get_discriminator_value(
            discriminator, index, parent
        )
        if discriminator_value is not None:
            return self._discriminator_mapping[discriminator]["value_id_map"][
                discriminator_value
            ]
        else:
            return 0

    def get_value_for(self, discriminator: str, id) -> str:
        if discriminator not in self._discriminator_mapping:
            return None
        return self._discriminator_mapping[discriminator]["id_value_map"][id]

    def _figure_out_partial_discriminator_index_mapping(
        self, discriminators: List[str], unique_values: dict[str, List[Any]]
    ) -> dict[str, str]:
        ret = dict()

        marker_count = [
            (marker, len(uniques)) for marker, uniques in unique_values.items()
        ]
        marker_count.sort(key=lambda x: x[1], reverse=True)
        markers, _ = zip(*marker_count)

        if len(markers) > len(discriminators):
            raise ValueError(
                f"This package only supports up to {len(discriminators)} markers."
            )

        for index, marker in enumerate(markers):
            ret[discriminators[index]] = marker
        return ret

    def _map_values_to_id(self, values: List) -> dict[str, int]:
        return {value: idx for idx, value in enumerate(values)}
