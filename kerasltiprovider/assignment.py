import datetime
import logging
import os
import typing

import requests
from flask import current_app

from kerasltiprovider import context
from kerasltiprovider.exceptions import (
    SubmissionAfterDeadlineException,
    UnknownAssignmentException,
)
from kerasltiprovider.ingest import KerasAssignmentValidationSet
from kerasltiprovider.tracer import Tracer
from kerasltiprovider.types import AnyIDType, KerasBaseAssignment, PredType
from kerasltiprovider.utils import Datetime

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

logging.getLogger("tensorflow").setLevel(logging.ERROR)

log = logging.getLogger("kerasltiprovider")
log.addHandler(logging.NullHandler())


class KerasAssignment(KerasBaseAssignment):
    def __init__(
        self,
        name: str,
        identifier: AnyIDType,
        submission_deadline: typing.Optional[datetime.datetime] = None,
        grading_callback: typing.Optional[typing.Callable[[float], float]] = None,
        validation_dataset: typing.Optional[KerasAssignmentValidationSet] = None,
    ):
        super().__init__(identifier=identifier)
        self.name = name
        self.submission_deadline = submission_deadline
        self.grading_callback = grading_callback
        self.validation_dataset = validation_dataset

    @property
    def formatted(self) -> typing.Dict[str, typing.Any]:
        return dict(
            name=self.name,
            identifier=self.identifier,
            submission_deadline="None"
            if not self.submission_deadline
            else self.submission_deadline.isoformat(),
        )

    def rpc_validation_backend(
        self, route: str, data: typing.Optional[typing.Dict[str, typing.Any]] = None
    ) -> typing.Any:
        vhost = current_app.config.get("VALIDATOR_HOST")
        vport = current_app.config.get("VALIDATOR_PORT")
        response = requests.post(
            f"http://{vhost}:{vport}/internal/assignment/{self.identifier}{route}",
            json=data or dict(),
        )
        return response.json()

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
            accuracy = round(
                float(
                    self.rpc_validation_backend("/validate", data=predictions).get(
                        "accuracy", 0
                    )
                ),
                ndigits=2,
            )
            score = round(
                accuracy
                if not self.grading_callback
                else self.grading_callback(accuracy),
                ndigits=2,
            )
            scope.span.log_kv(dict(score=score, accuracy=accuracy))
            return accuracy, score


def find_assignment(assignment_id: AnyIDType) -> KerasAssignment:
    try:
        return [
            a for a in context.assignments if str(a.identifier) == str(assignment_id)
        ][0]
    except (TypeError, ValueError, IndexError):
        raise UnknownAssignmentException(
            f'Could not find assignment with id "{assignment_id}"'
        )
