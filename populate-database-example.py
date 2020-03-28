import logging
import os
import sys
import redis
import click

import numpy as np

# To silence tensorflow warnings
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("kerasltiprovider").setLevel(logging.DEBUG)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"


@click.command()
@click.option("--host", default="localhost", help="Redis database host")
@click.option("--port", default=6379, help="Redis database port")
@click.option("--db", default=1, help="Redis database to ingest into")
@click.option("--flush", default=False, help="Flush the database before ingestion")
def ingest(host: str, port: int, db: int, flush: bool) -> int:
    try:
        import tensorflow_datasets as tfds

        from kerasltiprovider.ingest import KerasAssignmentValidationSet
        from kerasltiprovider.processing import Augment
        from kerasltiprovider.selection import RandomSelectionStrategy
        from kerasltiprovider.validation import ValidationData

        database = redis.Redis(host=host, port=port, db=db, decode_responses=True)

        def tf_flowers_assignment_data():
            test_data = tfds.load(
                "tf_flowers", split="train[80%:100%]", as_supervised=True
            )

            # Data augmentation parameters
            # Generate 20 crop settings, ranging from a 1% to 20% crop.
            scales = list(np.arange(0.8, 1.0, 0.01))

            return KerasAssignmentValidationSet(
                # Identifier MUST be the same as the one used in your config!
                identifier="3",
                # Data used for validation
                validation_data=ValidationData(test_data, resize=(300, 300)),
                # Selection strategy used to choose `validation_set_size` items from the `validation_data`
                input_selection_strategy=RandomSelectionStrategy(seed=1234),
                input_postprocessing_steps=[Augment(rotate=10, zoom=scales)],
                # Size of the validation set used for calculating the accuracy
                validation_set_size=200,
            )

        validation_data = [tf_flowers_assignment_data()]

        if flush:
            print(f"Flushing database {db}")
            database.flushdb()
        for data in validation_data:
            print(f"Ingesting validation data for assignment {data.identifier}")
            data.ingest(database)
            print(f"Assignment {data.identifier} done.")
    except Exception as e:  # pragma: no cover
        raise click.ClickException(str(e))
    return 0


if __name__ == "__main__":
    sys.exit(ingest())  # pragma: no cover
