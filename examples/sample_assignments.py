"""
Example config file declaring assignments
See any of the services here `
"""
from kerasltiprovider.assignment import (
    KerasAssignment,
    ValidationData,
)
from kerasltiprovider.selection import RandomSelectionStrategy
from kerasltiprovider.processing import Augment
from kerasltiprovider.utils import interpolate_accuracy

import datetime
import os
import logging
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf
import tensorflow_datasets as tfds

logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("kerasltiprovider").setLevel(logging.DEBUG)


def np_mnist_assignment():
    mnist = tf.keras.datasets.mnist
    _, (test_images, test_labels) = mnist.load_data()
    test_images = test_images / 255.0

    def grading_func(accuracy):
        return round(
                    interpolate_accuracy(accuracy, min=0.0, max=0.8), ndigits=2
                )

    return KerasAssignment(
        name="Exercise 2: Build your second network",
        identifier="2",
        # Data used for validation
        validation_data=ValidationData.from_numpy(test_images, test_labels),
        # Selection strategy used to choose `validation_set_size` items from the `validation_data`
        input_selection_strategy=RandomSelectionStrategy(seed=20),
        # Size of the validation set used for calculating the accuracy
        validation_set_size=200,
        partial_loading=False,
        # Deadline for submission, later submission will not be accepted
        submission_deadline=datetime.datetime(
            year=2020, month=12, day=31, hour=23, minute=59
        ),
        grading_callback=grading_func
    )


def tf_woof_assignment():
    test_data = tfds.load('tf_flowers', split="train[80%:100%]", as_supervised=True)

    def grading_func(accuracy):
        return round(
                    interpolate_accuracy(accuracy, min=0.0, max=0.8), ndigits=2
                )

    # Data augmentation parameters
    # Generate 20 crop settings, ranging from a 1% to 20% crop.
    scales = list(np.arange(0.8, 1.0, 0.01))

    return KerasAssignment(
        name="Exercise 3: Build a complex network",
        identifier="3",
        # Data used for validation
        validation_data=ValidationData(test_data, resize=(300, 300)),
        # Selection strategy used to choose `validation_set_size` items from the `validation_data`
        input_selection_strategy=RandomSelectionStrategy(seed=1234),
        input_postprocessing_steps=[Augment(rotate=10, zoom=scales)],
        # Size of the validation set used for calculating the accuracy
        validation_set_size=200,
        partial_loading=True,
        # Deadline for submission, later submission will not be accepted
        submission_deadline=datetime.datetime(
            year=2020, month=12, day=31, hour=23, minute=59
        ),
        grading_callback=grading_func
    )


# This will be read into the config
ASSIGNMENTS = [tf_woof_assignment(), np_mnist_assignment()]
