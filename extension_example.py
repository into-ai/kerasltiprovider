from kerasltiprovider import KerasLTIProvider
from kerasltiprovider.assignment import (
    KerasAssignment,
    ValidationData,
)
from kerasltiprovider.selection import RandomSelectionStrategy

import datetime
from tensorflow import keras

from flask import Flask
from waitress import serve

# Create a flask app here and
app = Flask(__name__)


def assignment():
    mnist = keras.datasets.mnist
    _, (test_images, test_labels) = mnist.load_data()
    test_images = test_images / 255.0

    return KerasAssignment(
        name="Exercise 2: Build your second network",
        identifier=2,
        # Data used for validation
        validation_data=ValidationData(test_images, test_labels),
        # Selection strategy used to choose `validation_set_size` items from the `validation_data`
        input_selection_strategy=RandomSelectionStrategy(seed=20),
        # Size of the validation set used for calculating the accuracy
        validation_set_size=100,
        # Deadline for submission, later submission will not be accepted
        submission_deadline=datetime.datetime(
            year=2020, month=12, day=31, hour=23, minute=59
        ),
    )


provider_config = dict(
    PRODUCTION=False,
    ENABLE_DEBUG_LAUNCHER=True,
    TEMPLATE_PREFIX="",
    # You need to pass the PUBLIC_URL for redirects to work
    PUBLIC_URL="http://localhost:8080/",
)


provider = KerasLTIProvider(
    app=app, assignments=[assignment()], config=provider_config,
)

# This example shows how to integrate the blueprint into any flask project
# To add the required routes, just register the blueprint
app.register_blueprint(provider.blueprint(), url_prefix="/")  # kerasltiprovider


@app.route("/launch")
def launch():
    return "This is my special launch URL!"


@app.route("/my/other/content")
def content():
    return "This is my custom content right here!"


if __name__ == "__main__":
    # Alternatively, you can use the builtin flask web server
    # app.run(debug=False, host="localhost", port=8080)
    serve(app, host="localhost", port=8080)
