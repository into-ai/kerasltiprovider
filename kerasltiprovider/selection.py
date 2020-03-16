import random
import typing
from abc import ABC, abstractmethod

import numpy as np

from kerasltiprovider.assignment import ValidationData
from kerasltiprovider.utils import hash_matrix


class SelectionStrategy(ABC):
    @abstractmethod
    def select(self, size: int, validation_data: ValidationData) -> ValidationData:
        pass


class RandomSelectionStrategy(SelectionStrategy):
    def __init__(self, seed: typing.Optional[int] = None) -> None:
        self.seed = seed

    def select(self, size: int, validation_data: ValidationData) -> ValidationData:
        input_size = len(validation_data.matrices)
        if self.seed is not None:
            # Seed the random number generator so the selection can be altered but is otherwise fair and consistent
            random.seed(self.seed)
        if not input_size > 0:
            raise ValueError("Need at least some validation data for validation")
        if input_size < size:
            raise ValueError(
                f"Cannot validate {size} items with only {input_size} validation items"
            )

        # Sort by hash for stable results
        sort_map = {
            hash_matrix(matrix): i for i, matrix in enumerate(validation_data.matrices)
        }
        if len(sort_map) < size:
            raise ValueError(
                f"Cannot validate {size} items with only {len(sort_map)} unique validation items"
            )
        sorted_hashes = sorted(sort_map.keys())
        available_hashes = sorted_hashes.copy()
        selected_input_data = np.zeros(
            shape=(size, *validation_data.matrices[0].shape),
            dtype=validation_data.matrices.dtype,
        )
        selected_label_data = np.zeros(
            shape=(size, *validation_data.labels[0].shape),
            dtype=validation_data.labels.dtype,
        )
        for i in range(size):
            rand_hash = random.choice(available_hashes)
            available_hashes.remove(rand_hash)
            mapped_index = sort_map[rand_hash]
            selected_input_data[i] = validation_data.matrices[mapped_index]
            selected_label_data[i] = validation_data.labels[mapped_index]
        return ValidationData(selected_input_data, selected_label_data)
