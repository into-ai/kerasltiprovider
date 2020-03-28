import json
import typing
from typing import TYPE_CHECKING

import numpy as np
import redis
import tensorflow as tf

from kerasltiprovider.database import Database
from kerasltiprovider.exceptions import NoDatabaseException
from kerasltiprovider.types import AnyIDType, KerasBaseAssignment
from kerasltiprovider.utils import hash_matrix, input_key_for
from kerasltiprovider.validation import ValidationData

if TYPE_CHECKING:  # pragma: no cover
    from kerasltiprovider.selection import SelectionStrategy  # noqa: F401
    from kerasltiprovider.processing import PostprocessingStep  # noqa: F401


ValHTType = typing.Dict[str, typing.Dict[str, str]]
PredType = typing.Dict[str, int]
VDC = typing.TypeVar("VDC", bound="ValidationData")


class KerasAssignmentValidationSet(KerasBaseAssignment):
    def __init__(
        self,
        identifier: AnyIDType,
        validation_data: ValidationData,
        input_selection_strategy: "SelectionStrategy",
        validation_set_size: int,
        input_postprocessing_steps: typing.Optional[
            typing.List["PostprocessingStep"]
        ] = None,
    ):
        super().__init__(identifier=identifier)
        self.validation_set_size = validation_set_size
        self.input_selection_strategy = input_selection_strategy
        self.validation_data = validation_data

        # Selected validation set
        self.validation_set = self.input_selection_strategy.select(
            self.validation_set_size, self.validation_data
        )

        for postprocessing_step in input_postprocessing_steps or list():
            self.validation_set = postprocessing_step.process(self.validation_set)

        # Fix changes to shapes during data augmentation
        if self.validation_data.size is not None:
            self.validation_set.dataset = self.validation_set.dataset.map(
                lambda i, l: (tf.image.resize(i, self.validation_data.size), l)
            )

        # Hashed validation set (will only be calculated once on demand)
        self._validation_hash_table: ValHTType = dict()

    def validation_hash_table(self) -> ValHTType:
        if len(self._validation_hash_table) > 0:
            return self._validation_hash_table
        for matrix, label in self.validation_set.items():
            self._validation_hash_table[hash_matrix(matrix)] = dict(
                matrix=matrix.numpy(), predicted=label
            )
        return self._validation_hash_table

    def connect_and_ingest(
        self, hostname: str = "localhost", port: int = 6379,
    ) -> None:
        db = redis.Redis(host=hostname, port=port, db=1, decode_responses=True)
        self.ingest(db)

    def ingest(self, db: typing.Optional[redis.Redis] = None) -> None:
        _db = db or Database.assignments
        if not _db:
            raise NoDatabaseException("No database for ingestion")
        with _db.pipeline() as pipe:
            for matrix_hash, request in self.validation_hash_table().items():
                try:
                    input_matrix: np.ndarray = request["matrix"]
                    assert isinstance(input_matrix, np.ndarray)
                    predicted_class = int(request["predicted"])
                    pipe.hset(
                        input_key_for(self.identifier, matrix_hash),
                        "input",
                        json.dumps(input_matrix.tolist()),
                    )
                    pipe.hset(
                        input_key_for(self.identifier, matrix_hash),
                        "hash",
                        matrix_hash,
                    )
                    pipe.hset(
                        input_key_for(self.identifier, matrix_hash),
                        "predicted",
                        predicted_class,
                    )
                except Exception as e:
                    raise e
            pipe.execute()
