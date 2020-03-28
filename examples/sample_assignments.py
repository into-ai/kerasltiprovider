"""
Example config file declaring assignments
See any of the services here `
"""
from kerasltiprovider.assignment import KerasAssignment, KerasAssignmentValidationSet
from kerasltiprovider.validation import ValidationData
from kerasltiprovider.selection import RandomSelectionStrategy
from kerasltiprovider.utils import interpolate_accuracy

import datetime
import os
import logging

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf

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

    identifier = "2"
    return KerasAssignment(
        name="Exercise 2: Build your second network",
        identifier=identifier,
        # Data used for validation
        validation_dataset=KerasAssignmentValidationSet(
            identifier=identifier,
            validation_data=ValidationData.from_numpy(test_images, test_labels),
            # Selection strategy used to choose `validation_set_size` items from the `validation_data`
            input_selection_strategy=RandomSelectionStrategy(seed=20),
            # Size of the validation set used for calculating the accuracy
            validation_set_size=200,
        ),
        partial_loading=False,
        # Deadline for submission, later submission will not be accepted
        submission_deadline=datetime.datetime(
            year=2020, month=12, day=31, hour=23, minute=59
        ),
        grading_callback=grading_func
    )


def tf_flowers_assignment():
    def grading_func(accuracy):
        return round(
                    interpolate_accuracy(accuracy, min=0.0, max=0.8), ndigits=2
                )
    return KerasAssignment(
        name="Exercise 3: Build a complex network",
        identifier="3",
        # This dataset is big and expensive for lower end machines
        # If no `validation_dataset` is given, the assignment's validation data is expected to exist in the database
        # You can connect to the redis database and remotely insert the data.
        # Have a look at the `populate-database-example.py`.
        validation_dataset=None,
        partial_loading=True,
        # Deadline for submission, later submission will not be accepted
        submission_deadline=datetime.datetime(
            year=2020, month=12, day=31, hour=23, minute=59
        ),
        grading_callback=grading_func
    )


# This will be read into the config
ASSIGNMENTS = [tf_flowers_assignment(), np_mnist_assignment()]
