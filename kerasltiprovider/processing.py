import math
import typing
from abc import ABC, abstractmethod

import numpy as np
import tensorflow as tf

from kerasltiprovider.assignment import ValidationData


class PostprocessingStep(ABC):
    @abstractmethod
    def process(self, validation_data: ValidationData) -> ValidationData:
        pass


class Augment(PostprocessingStep):
    def __init__(self, **augment_options: typing.Any):
        self.augment_options = augment_options

    def process(self, validation_data: ValidationData) -> ValidationData:
        batch_size = 30
        data_generator = tf.keras.preprocessing.image.ImageDataGenerator(
            **self.augment_options
        )
        generated = data_generator.flow(
            validation_data.matrices, validation_data.labels, batch_size=batch_size
        )
        number_of_generator_calls = math.ceil(
            len(validation_data.matrices) / float(batch_size)
        )
        augmented_inputs = []

        for i in range(0, int(number_of_generator_calls)):
            augmented_inputs.extend(np.array(generated[i][0]))
        return ValidationData(np.array(augmented_inputs), validation_data.labels)
