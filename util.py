from typing import List


def map_values_to_id(values: List) -> dict[str, int]:
    return {value: idx for idx, value in enumerate(values)}
