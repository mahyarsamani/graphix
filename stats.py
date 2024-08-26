from typing import List, Set, Union
from warnings import warn

from .base_types import AggregatorNode, Node, Stat
from .compare_util import BiggestThing, SmallestThing


class Scalar(Stat):
    def __init__(self, index: dict, name: str) -> None:
        super().__init__(index, name, "Scalar")

    def process_dict(self, parent: Node, key: str, value: dict) -> None:
        assert self._name == key
        self._value[parent] = value["value"]
        self._parents.append(parent)

    def filter_parents(
        self, these_parents: Set[Node], not_these_parents: Set[Node]
    ) -> List[Node]:
        if these_parents and not_these_parents:
            raise ValueError(
                "Either these_parents or not_these_parents should be empty"
            )

        new_value = dict()
        for parent, value in self._value.items():
            if not these_parents and parent in these_parents:
                new_value[parent] = value
            if not not_these_parents and parent not in not_these_parents:
                new_value[parent] = value
        to_ret = Scalar(self._index, self._name)
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret

    def dropna(self) -> "Scalar":
        new_value = {
            parent: value
            for parent, value in self._value.items()
            if isinstance(value, (int, float))
        }

        to_ret = Scalar(self._index, self._name)
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret

    def aggregate_using(self, aggregator: AggregatorNode) -> None:
        return aggregator.aggregate(self)

    def __add__(self, other: Union["Scalar", int, float]) -> "Scalar":
        if isinstance(other, Stat):
            if not isinstance(other, Scalar):
                raise ValueError(
                    "You can only add a Scalar to another Scalar."
                )
            if self._index != other.index():
                raise ValueError(
                    "Indices of the two Scalars are not the same. "
                    "This means they are from different simluation runs."
                )
            if set(self._parents) != set(other.parents()):
                raise ValueError(
                    "Parents of the two Scalars are not the same, "
                    "if you need to create a new stat that takes two "
                    "stats with different parents, you need to do "
                    "that using meld function."
                )

            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] + other.value()[parent]
            to_ret = Scalar(self._index, f"({self._name} + {other.name()})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        elif isinstance(other, (int, float)):
            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] + other
            to_ret = Scalar(self._index, f"({self._name} + {other})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        else:
            raise ValueError("You can only add a Scalar or a number.")

    def __sub__(self, other: Union["Scalar", int, float]) -> "Scalar":
        if isinstance(other, Stat):
            if not isinstance(other, Scalar):
                raise ValueError("You can only subtract two Scalars.")
            if self._index != other.index():
                raise ValueError(
                    "Indices of the two Scalars are not the same."
                )
            if set(self._parents) != set(other.parents()):
                raise ValueError(
                    "Parents of the two Scalars are not the same, "
                    "if you need to create a new stat that takes two "
                    "stats with different parents, you need to do "
                    "that using meld function."
                )

            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] - other.value()[parent]
            to_ret = Scalar(self._index, f"({self._name} - {other.name()})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        elif isinstance(other, (int, float)):
            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] - other
            to_ret = Scalar(self._index, f"({self._name} - {other})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        else:
            raise ValueError("You can only subtract a Scalar or a number.")

    def __mul__(self, other: Union["Scalar", int, float]) -> "Scalar":
        if isinstance(other, Stat):
            if not isinstance(other, Scalar):
                raise ValueError("You can only multiply two Scalars.")
            if self._index != other.index():
                raise ValueError(
                    "Indices of the two Scalars are not the same."
                )
            if set(self._parents) != set(other.parents()):
                raise ValueError(
                    "Parents of the two Scalars are not the same, "
                    "if you need to create a new stat that takes two "
                    "stats with different parents, you need to do "
                    "that using meld function."
                )

            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] * other.value()[parent]
            to_ret = Scalar(self._index, f"({self._name} * {other.name()})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        elif isinstance(other, (int, float)):
            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] * other
            to_ret = Scalar(self._index, f"({self._name} * {other})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        else:
            raise ValueError("You can only multiply a Scalar or a number.")

    def __truediv__(self, other: Union["Scalar", int, float]) -> "Scalar":
        if isinstance(other, Stat):
            if not isinstance(other, Scalar):
                raise ValueError("You can only divide two Scalars.")
            if self._index != other.index():
                raise ValueError(
                    "Indices of the two Scalars are not the same."
                )
            if set(self._parents) != set(other.parents()):
                raise ValueError(
                    "Parents of the two Scalars are not the same, "
                    "if you need to create a new stat that takes two "
                    "stats with different parents, you need to do "
                    "that using meld function."
                )

            new_value = dict()
            for parent in self._parents:
                try:
                    new_value[parent] = (
                        self._value[parent] / other.value()[parent]
                    )
                except ZeroDivisionError:
                    new_value[parent] = "inf"
            to_ret = Scalar(self._index, f"({self._name} / {other.name()})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        elif isinstance(other, (int, float)):
            new_value = dict()
            for parent in self._parents:
                try:
                    new_value[parent] = self._value[parent] / other
                except ZeroDivisionError:
                    new_value[parent] = "inf"
            to_ret = Scalar(self._index, f"({self._name} / {other})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        else:
            raise ValueError("You can only divide a Scalar or a number.")

    def __floordiv__(self, other: Union["Scalar", int, float]) -> "Scalar":
        if isinstance(other, Stat):
            if not isinstance(other, Scalar):
                raise ValueError("You can only floor divide two Scalars.")
            if self._index != other.index():
                raise ValueError(
                    "Indices of the two Scalars are not the same."
                )
            if set(self._parents) != set(other.parents()):
                raise ValueError(
                    "Parents of the two Scalars are not the same, "
                    "if you need to create a new stat that takes two "
                    "stats with different parents, you need to do "
                    "that using meld function."
                )

            new_value = dict()
            for parent in self._parents:
                try:
                    new_value[parent] = self._value[parent] / other
                except ZeroDivisionError:
                    new_value[parent] = "inf"
            to_ret = Scalar(self._index, f"({self._name} // {other.name()})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        elif isinstance(other, (int, float)):
            new_value = dict()
            try:
                new_value[parent] = self._value[parent] / other
            except ZeroDivisionError:
                new_value[parent] = "inf"
            to_ret = Scalar(self._index, f"({self._name} // {other})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        else:
            raise ValueError("You can only floor divide a Scalar or a number.")

    def __pow__(self, other: Union["Scalar", int, float]) -> "Scalar":
        if isinstance(other, Stat):
            if not isinstance(other, Scalar):
                raise ValueError("You can only power two Scalars.")
            if self._index != other.index():
                raise ValueError(
                    "Indices of the two Scalars are not the same."
                )
            if set(self._parents) != set(other.parents()):
                raise ValueError(
                    "Parents of the two Scalars are not the same, "
                    "if you need to create a new stat that takes two "
                    "stats with different parents, you need to do "
                    "that using meld function."
                )

            new_value = dict()
            for parent in self._parents:
                new_value[parent] = (
                    self._value[parent] ** other.value()[parent]
                )
            to_ret = Scalar(self._index, f"({self._name} ** {other.name()})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        elif isinstance(other, (int, float)):
            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] ** other
            to_ret = Scalar(self._index, f"{self._name} ** {other}")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        else:
            raise ValueError("You can only power a Scalar or a number.")

    def __mod__(self, other: Union["Scalar", int, float]) -> "Scalar":
        if isinstance(other, Stat):
            if not isinstance(other, Scalar):
                raise ValueError("You can only mod two Scalars.")
            if self._index != other.index():
                raise ValueError(
                    "Indices of the two Scalars are not the same."
                )
            if set(self._parents) != set(other.parents()):
                raise ValueError(
                    "Parents of the two Scalars are not the same, "
                    "if you need to create a new stat that takes two "
                    "stats with different parents, you need to do "
                    "that using meld function."
                )

            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] % other.value()[parent]
            to_ret = Scalar(self._index, f"({self._name} % {other.name()})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        elif isinstance(other, (int, float)):
            new_value = dict()
            for parent in self._parents:
                new_value[parent] = self._value[parent] % other
            to_ret = Scalar(self._index, f"({self._name} % {other})")
            to_ret._set_value(new_value)
            to_ret._set_parents(list(new_value.keys()))
            return to_ret
        else:
            raise ValueError("You can only mod a Scalar or a number.")


class Distribution(Stat):
    class Bucket:
        def __init__(self, start: int, end: int, freq: int) -> None:
            self._start = start
            self._end = end
            self._freq = freq

        def lower_bound(self) -> int:
            return self._start

        def upper_bound(self) -> int:
            return self._end

        def freq(self):
            return self._freq

        def size(self):
            return self._end - self._start

        def overlap_size(self, other: "Distribution.Bucket") -> int:
            return max(
                0,
                min(self._end, other.upper_bound())
                - max(self._start, other.lower_bound()),
            )

        def combine_with(self, other: "Distribution.Bucket") -> None:
            assert self.overlap_size(other) > 0
            if self.overlap_size(other) < other.size():
                warn(f"Merging bucket {other} with {self} is not perfect.")
            self._freq += other.freq()

        def __str__(self):
            return f"Bucket(start: {self._start}, end: {self._end}, freq: {self._freq})"

        def __repr__(self):
            return self.__str__()

    def __init__(self, index: dict, name: str) -> None:
        super().__init__(index, name, "Distribution")

    def process_dict(self, parent: Node, key: str, value: dict) -> None:
        assert self._name == key
        assert value["num_bins"] == len(value["value"])
        bin_size = value["bin_size"]
        min_val = value["min"]
        buckets = [
            Distribution.Bucket(
                min_val + i * bin_size, min_val + (i + 1) * bin_size, freq
            )
            for i, freq in enumerate(value["value"])
        ]
        self._value[parent] = buckets
        self._parents.append(parent)

    def filter_parents(
        self, these_parents: Set[Node], not_these_parents: Set[Node]
    ) -> Stat:
        if these_parents and not_these_parents:
            raise ValueError(
                "Either these_parents or not_these_parents should be empty"
            )

        new_value = dict()
        for parent, value in self._value.items():
            if these_parents and parent in these_parents:
                new_value[parent] = value
            if not_these_parents and parent not in not_these_parents:
                new_value[parent] = value
        to_ret = Distribution(self._index, self._name)
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret

    def aggregate_using(
        self,
        aggregator_node: AggregatorNode,
    ) -> None:
        return aggregator_node.aggregate(self)

    def __add__(self, other: "Distribution") -> "Distribution":
        raise RuntimeError("You should not add two Distribution stats.")

    def __sub__(self, other: Stat) -> Stat:
        raise RuntimeError("You should not subtract two Distribution stats.")

    def __mul__(self, other: Stat) -> Stat:
        raise RuntimeError("You should not multiply two Distribution stats.")

    def __truediv__(self, other: Stat) -> Stat:
        raise RuntimeError("You should not divide two Distribution stats.")

    def __floordiv__(self, other: Stat) -> Stat:
        raise RuntimeError(
            "You should not floor divide two Distribution stats."
        )

    def __pow__(self, other: Stat) -> Stat:
        raise RuntimeError("You should not power two Distribution stats.")

    def __mod__(self, other: Stat) -> Stat:
        raise RuntimeError("You should not mod two Distribution stats.")


# TODO: Add class for Vector stats.
