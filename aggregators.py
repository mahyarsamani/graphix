from math import ceil
from statistics import geometric_mean, mean
from warnings import warn

from .base_types import AggregatorNode
from .compare_util import BiggestThing, SmallestThing
from .stats import Distribution, Scalar


class SummationAggregator(AggregatorNode):
    def __init__(self) -> None:
        super().__init__("SummationAggregator", "Stats::SummationAggregator")

    def aggregate(self, stat: Scalar) -> Scalar:
        if not isinstance(stat, Scalar):
            raise RuntimeError(
                "SummationAggregator should only be used to aggregate a Scalar."
            )

        warn(
            "SummationAggregator will drop na values from the original stats."
        )
        nona_stat = stat.dropna()
        new_value = nona_stat.value().copy()
        new_value.update({self: sum(nona_stat.value().values())})
        to_ret = Scalar(nona_stat.index(), nona_stat.name())
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret


class ArithmeticMeanAggregator(AggregatorNode):
    def __init__(self) -> None:
        super().__init__(
            "ArithmeticMeanAggregator", "Stats::ArithmeticMeanAggregator"
        )

    def aggregate(self, stat: Scalar) -> Scalar:
        if not isinstance(stat, Scalar):
            raise RuntimeError(
                "ArithmeticMeanAggregator should only be used to aggregate a Scalar."
            )

        warn(
            "ArithmeticMeanAggregator will drop na values from the original stats."
        )
        nona_stat = stat.dropna()
        new_value = nona_stat.value().copy()
        new_value.update({self: mean(nona_stat.value().values())})
        to_ret = Scalar(nona_stat.index(), nona_stat.name())
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret


class GeometricMeanAggregator(AggregatorNode):
    def __init__(self) -> None:
        super().__init__(
            "GeometricMeanAggregator", "Stats::GeometricMeanAggregator"
        )

    def aggregate(self, stat: Scalar) -> Scalar:
        if not isinstance(stat, Scalar):
            raise RuntimeError(
                "GeometricMeanAggregator should only be used to aggregate a Scalar."
            )

        warn(
            "GeometricMeanAggregator will drop na values from the original stats."
        )
        nona_stat = stat.dropna()
        new_value = nona_stat.value().copy()
        new_value.update({self: geometric_mean(nona_stat.value().values())})
        to_ret = Scalar(nona_stat.index(), nona_stat.name())
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret


class MinAggregator(AggregatorNode):
    def __init__(self) -> None:
        super().__init__("MinAggregator", "Stats::MinAggregator")

    def aggregate(self, stat: Scalar) -> Scalar:
        if not isinstance(stat, Scalar):
            raise RuntimeError(
                "MinAggregator should only be used to aggregate a Scalar."
            )

        warn("MinAggregator will drop na values from the original stats.")
        nona_stat = stat.dropna()
        new_value = nona_stat.value().copy()
        new_value.update({self: min(nona_stat.value().values())})
        to_ret = Scalar(nona_stat.index(), nona_stat.name())
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret


# This is the best aggregator ever
class MaxAggregator(AggregatorNode):
    def __init__(self) -> None:
        super().__init__("MaxAggregator", "Stats::MaxAggregator")

    def aggregate(self, stat: Scalar) -> Scalar:
        if not isinstance(stat, Scalar):
            raise RuntimeError(
                "MaxAggregator should only be used to aggregate a Scalar."
            )

        warn("MaxAggregator will drop na values from the original stats.")
        nona_stat = stat.dropna()
        new_value = nona_stat.value().copy()
        new_value.update({self: max(nona_stat.value().values())})
        to_ret = Scalar(nona_stat.index(), nona_stat.name())
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret


class CombineAggregator(AggregatorNode):
    def __init__(self) -> None:
        super().__init__("CombineAggregator", "Stats::CombineAggregator")

    def aggregate(self, stat: Distribution) -> Distribution:
        if not isinstance(stat, Distribution):
            raise RuntimeError(
                "CombineAggregator should only be used to aggregate a Distribution."
            )
        min_start = BiggestThing()
        max_end = SmallestThing()
        bin_size = SmallestThing()

        for _, buckets in stat.value().items():
            min_start = int(min(min_start, buckets[0].lower_bound()))
            max_end = int(max(max_end, buckets[-1].upper_bound()))
            bin_size = int(max(bin_size, buckets[0].size()))
        num_bins = ceil((max_end - min_start) / bin_size)

        new_value = stat.value().copy()
        buckets = [
            Distribution.Bucket(
                min_start + i * bin_size, min_start + (i + 1) * bin_size, 0
            )
            for i in range(num_bins)
        ]
        for _, buckets_to_merge in stat.value().items():
            for bucket in buckets_to_merge:
                index_0 = int((bucket.lower_bound() - min_start) / bin_size)
                # This one can be out of bounds, we also know that
                # 0 <= index_1 - index_0 <= 1. So in case this is out of bounds
                # we are looking at the last bucket twice.
                index_1 = min(
                    num_bins - 1,
                    int((bucket.upper_bound() - min_start) / bin_size),
                )
                overlap_0 = bucket.overlap_size(buckets[index_0])
                overlap_1 = bucket.overlap_size(buckets[index_1])
                if overlap_0 == 0 and overlap_1 == 0:
                    raise RuntimeError(
                        "The bucket does not overlap with any of the buckets.\n"
                        f"to_merge: {bucket}, buckets[{index_0}]: {buckets[index_0]}, buckets[{index_1}]: {buckets[index_1]}"
                    )
                index = index_0 if overlap_0 > overlap_1 else index_1
                buckets[index].combine_with(bucket)
        new_value.update({self: buckets})

        to_ret = Distribution(stat.index(), stat.name())
        to_ret._set_value(new_value)
        to_ret._set_parents(list(new_value.keys()))
        return to_ret
