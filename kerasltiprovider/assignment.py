import datetime
import json
import logging
import os
import typing
from typing import TYPE_CHECKING

import numpy as np
import tensorflow as tf

from kerasltiprovider import context
from kerasltiprovider.database import Database
from kerasltiprovider.exceptions import (
    NoDatabaseException,
    SubmissionAfterDeadlineException,
    SubmissionValidationError,
    UnknownAssignmentException,
    UnknownDatasetException,
)
from kerasltiprovider.tracer import Tracer
from kerasltiprovider.types import AnyIDType
from kerasltiprovider.utils import Datetime, hash_matrix

if TYPE_CHECKING:  # pragma: no cover
    from kerasltiprovider.selection import SelectionStrategy  # noqa: F401
    from kerasltiprovider.processing import PostprocessingStep  # noqa: F401

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

logging.getLogger("tensorflow").setLevel(logging.ERROR)

log = logging.getLogger("kerasltiprovider")
log.addHandler(logging.NullHandler())


ValHTType = typing.Dict[str, typing.Dict[str, str]]
PredType = typing.Dict[str, int]
VDC = typing.TypeVar("VDC", bound="ValidationData")


class ValidationData:
    def __init__(
        self,
        ds: tf.data.Dataset,
        resize: typing.Optional[typing.Tuple[int, ...]] = None,
    ) -> None:
        self.dataset = ds
        self.size = resize
        if resize is not None:
            self.dataset = self.dataset.map(
                lambda i, l: (tf.image.resize(i, resize), l)
            )

    @classmethod
    def from_numpy(
        cls: typing.Type[VDC], matrices: np.ndarray, labels: np.ndarray,
    ) -> VDC:
        assert matrices.shape[0] == labels.shape[0]
        dataset = tf.data.Dataset.from_tensor_slices((matrices, labels))
        return cls(dataset)

    @classmethod
    def from_model(cls: typing.Type[VDC], model_file: str, matrices: np.ndarray) -> VDC:
        model = tf.keras.models._load_model(model_file)
        predictions = model.predict(matrices)
        predicted_classes = np.array([np.argmax(p) for p in predictions])
        return cls(matrices, predicted_classes)

    def items(self) -> tf.data.Dataset:
        return self.dataset


class KerasAssignment:
    def __init__(
        self,
        name: str,
        identifier: AnyIDType,
        validation_data: ValidationData,
        input_selection_strategy: "SelectionStrategy",
        validation_set_size: int,
        partial_loading: typing.Optional[bool] = False,
        input_postprocessing_steps: typing.Optional[
            typing.List["PostprocessingStep"]
        ] = None,
        submission_deadline: typing.Optional[datetime.datetime] = None,
        grading_callback: typing.Optional[typing.Callable[[float], float]] = None,
    ):
        self.name = name
        self.identifier = identifier
        self.validation_set_size = validation_set_size
        self.submission_deadline = submission_deadline
        self.partial_loading = partial_loading
        self.input_selection_strategy = input_selection_strategy
        self.grading_callback = grading_callback

        # The raw validation data (inputs and labels)
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

    @property
    def formatted(self) -> typing.Dict[str, typing.Any]:
        return dict(
            name=self.name,
            identifier=self.identifier,
            validation_set_size=self.validation_set_size,
            submission_deadline="None"
            if not self.submission_deadline
            else self.submission_deadline.isoformat(),
            input_selection_strategy=self.input_selection_strategy.__class__.__name__,
            validation_hash_table_preview=list(self.validation_hash_table.items())[:1],
        )

    @property
    def validation_hash_table(self) -> ValHTType:
        if len(self._validation_hash_table) > 0:
            return self._validation_hash_table
        for matrix, label in self.validation_set.items():
            self._validation_hash_table[hash_matrix(matrix)] = dict(
                matrix=matrix, predicted=label
            )
        return self._validation_hash_table

    def still_open(self, date: typing.Optional[Datetime] = None) -> bool:
        with Tracer.main().start_active_span("KerasAssignment.still_open") as scope:
            if self.submission_deadline is None:
                return True
            scope.span.set_tag("date", date)
            date = date or Datetime.now()
            diff = (self.submission_deadline - date).total_seconds()
            scope.span.log_kv(dict(diff_seconds=diff, still_open=diff >= 0))
            return diff >= 0

    def validate(self, predictions: PredType) -> typing.Tuple[float, float]:
        with Tracer.main().start_active_span("KerasAssignment.validate") as scope:
            scope.span.set_tag("predictions", predictions)
            if not self.still_open():
                raise SubmissionAfterDeadlineException(
                    f"The deadline for submission was on {'?' if not self.submission_deadline else self.submission_deadline.isoformat()}"
                )
            if not len(predictions) == self.validation_set_size:
                raise SubmissionValidationError(
                    f"Expected {self.validation_set_size} predictions"
                )
            num_correct = 0
            if not Database.assignments:
                raise NoDatabaseException
            for matrix_hash, prediction in predictions.items():
                reference_prediction = Database.assignments.hget(
                    self.input_key_for(matrix_hash), "predicted"
                )
                if reference_prediction is None:
                    raise UnknownDatasetException(
                        "Cannot validate your results. Is this the correct assignment?"
                    )
                elif prediction is None:
                    pass
                else:
                    if float(reference_prediction) == float(prediction):
                        num_correct += 1

            accuracy = round(num_correct / self.validation_set_size, ndigits=2)
            score = round(
                accuracy
                if not self.grading_callback
                else self.grading_callback(accuracy),
                ndigits=2,
            )
            scope.span.log_kv(
                dict(num_correct=num_correct, score=score, accuracy=accuracy)
            )
            return accuracy, score

    def input_key_for(self, matrix_hash: str) -> str:
        return f"{self.identifier}:{matrix_hash}"

    def save_validation_hash_table(self) -> None:
        with Tracer.main().start_span(
            "KerasAssignment.save_validation_hash_table"
        ) as _:
            if not Database.assignments:
                raise NoDatabaseException
            with Database.assignments.pipeline() as pipe:
                # Save to redis key value database
                for matrix_hash, request in self.validation_hash_table.items():
                    try:
                        _input_matrix: tf.Tensor = request["matrix"]
                        input_matrix = _input_matrix.numpy()
                        assert isinstance(input_matrix, np.ndarray)
                        predicted_class = int(request["predicted"])
                        pipe.hset(
                            self.input_key_for(matrix_hash),
                            "input",
                            json.dumps(input_matrix.tolist()),
                        )
                        pipe.hset(
                            self.input_key_for(matrix_hash),
                            "predicted",
                            predicted_class,
                        )
                    except Exception as e:
                        raise e
                pipe.execute()


def find_assignment(assignment_id: AnyIDType) -> KerasAssignment:
    try:
        return [
            a for a in context.assignments if str(a.identifier) == str(assignment_id)
        ][0]
    except (TypeError, ValueError, IndexError):
        raise UnknownAssignmentException(
            f'Could not find assignment with id "{assignment_id}"'
        )
