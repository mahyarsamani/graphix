from abc import abstractmethod
from typing import final, List, Set

from .singleton_meta import SingletonMeta


class GroupNode:
    _instance_number = -1

    @classmethod
    def get_id(cls) -> int:
        cls._instance_number += 1
        return cls._instance_number

    def __init__(self, name: str, path: str) -> None:
        self._name = name
        self._path = path.lstrip(".")
        self._id = GroupNode.get_id()
        self._children = []

    def add_child(self, child: "GroupNode") -> None:
        self._children.append(child)

    def name(self) -> str:
        return self._name

    def path(self) -> str:
        return self._path

    def id(self) -> int:
        return self._id

    def children(self) -> List["GroupNode"]:
        return self._children

    def __eq__(self, other: "GroupNode") -> bool:
        return self._path == other.path()

    def __lt__(self, other: "GroupNode") -> bool:
        return len(self._path.split(".")) < len(other.path().split("."))

    def __gt__(self, other: "GroupNode") -> bool:
        return len(self._path.split(".")) > len(other.path().split("."))

    def __hash__(self) -> int:
        return hash(self._path)

    def __str__(self) -> str:
        return f"GroupNode(name: {self._name}, path: {self._path}, children: {self._children})"

    def __repr__(self) -> str:
        return self.__str__()


class AggregatorNode(GroupNode, metaclass=SingletonMeta):
    def __init__(self, name: str, path: str) -> None:
        super().__init__(name, path)

    @final
    def add_child(self, child: GroupNode) -> None:
        raise RuntimeError("You should not add a child to an AggregatorNode.")

    @abstractmethod
    def aggregate(self, stat: "Stat") -> "Stat":
        raise NotImplementedError

    def __str__(self) -> str:
        return f"AggregatorNode(name: {self._name}, path: {self._path})"

    def __repr__(self) -> str:
        return self.__str__()


class Stat:
    def __init__(self, index: dict, name: str, type: str) -> None:
        self._index = index
        self._name = name
        self._type = type
        self._value = dict()
        self._parents = []

    @abstractmethod
    def process_dict(self, parent: GroupNode, key: str, value: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def filter_parents(
        self,
        these_parents: Set[GroupNode],
        not_these_parents: Set[GroupNode],
    ) -> "Stat":
        raise NotImplementedError

    @abstractmethod
    def aggregate_using(self, aggregator: AggregatorNode) -> None:
        raise NotImplementedError

    @abstractmethod
    def dropna(self) -> "Stat":
        raise NotImplementedError

    def index(self) -> dict:
        return self._index

    def name(self) -> str:
        return self._name

    def value(self) -> dict:
        return self._value

    def parents(self) -> List[GroupNode]:
        return self._parents

    def __str__(self) -> str:
        return f"{self._type}(name: {self._name}, value: {self._value})"

    def __repr__(self) -> str:
        return self.__str__()

    def _set_value(self, value: dict) -> None:
        self._value = value

    def _set_parents(self, parents: List[GroupNode]) -> None:
        self._parents = parents

    def __add__(self, other: "Stat") -> "Stat":
        raise NotImplementedError

    def __sub__(self, other: "Stat") -> "Stat":
        raise NotImplementedError

    def __mul__(self, other: "Stat") -> "Stat":
        raise NotImplementedError

    def __truediv__(self, other: "Stat") -> "Stat":
        raise NotImplementedError

    def __floordiv__(self, other: "Stat") -> "Stat":
        raise NotImplementedError

    def __pow__(self, other: "Stat") -> "Stat":
        raise NotImplementedError

    def __mod__(self, other: "Stat") -> "Stat":
        raise NotImplementedError
