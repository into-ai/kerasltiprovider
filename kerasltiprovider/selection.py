import typing
from abc import ABC, abstractmethod

import tensorflow as tf

from kerasltiprovider.assignment import ValidationData


class SelectionStrategy(ABC):
    @abstractmethod
    def select(self, size: int, validation_data: ValidationData) -> ValidationData:
        pass


class RandomSelectionStrategy(SelectionStrategy):
    def __init__(self, seed: typing.Optional[int] = None) -> None:
        self.seed = seed

    def select(self, size: int, validation_data: ValidationData) -> ValidationData:
        tf.random.set_seed(self.seed)
        return ValidationData(validation_data.dataset.take(size))
