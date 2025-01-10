from abc import abstractmethod
from typing import Any


from .singleton_meta import SingletonMeta


class ComparableThing(metaclass=SingletonMeta):
    def __eq__(self, other: Any) -> bool:
        return other is self

    @abstractmethod
    def __gt__(self, other: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def __lt__(self, other: Any) -> bool:
        raise NotImplementedError

    def __ge__(self, other: Any) -> bool:
        return self.__gt__() or self.__eq__()

    def __le__(self, other: Any) -> bool:
        return self.__lt__() or self.__eq__()


class SmallestThing(ComparableThing):
    def __gt__(self, other: Any) -> bool:
        return False

    def __lt__(self, other: Any) -> bool:
        return True


class BiggestThing(ComparableThing):
    def __gt__(self, other: Any) -> bool:
        return True

    def __lt__(self, other: Any) -> bool:
        return False
