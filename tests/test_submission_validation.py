import datetime
import typing
import unittest.mock
from contextlib import contextmanager

import fakeredis
import numpy as np
import pytest

from kerasltiprovider.assignment import KerasAssignment, ValidationData
from kerasltiprovider.exceptions import (
    SubmissionAfterDeadlineException,
    SubmissionValidationError,
)
from kerasltiprovider.selection import RandomSelectionStrategy
from kerasltiprovider.utils import Datetime, hash_matrix, interpolate_accuracy


def to_matrix(x: typing.List[int], y: typing.List[int]) -> np.ndarray:
    return np.array([x, y], np.int32)


@contextmanager
def mock_redis_connection() -> typing.Iterator[
    typing.Tuple[unittest.mock.PropertyMock, unittest.mock.PropertyMock]
]:
    with unittest.mock.patch(
        "kerasltiprovider.database.Database.assignments",
        new_callable=unittest.mock.PropertyMock,
    ) as mocked_assignments_db:
        with unittest.mock.patch(
            "kerasltiprovider.database.Database.users",
            new_callable=unittest.mock.PropertyMock,
        ) as mocked_users_db:
            mocked_assignments_db.return_value = fakeredis.FakeStrictRedis()
            mocked_users_db.return_value = fakeredis.FakeStrictRedis()
            yield mocked_assignments_db, mocked_users_db


@pytest.fixture
def mock_assignment1() -> KerasAssignment:
    validation_data = np.array([[4, 5, 6], [1, 2, 3]])
    # validation_label = np.array([[4, 5, 6], [1, 2, 3]])
    validation_label = np.array([1, 2])
    with unittest.mock.patch(
        "kerasltiprovider.assignment.KerasAssignment"
    ) as mocked_model:
        mocked_model.return_value = unittest.mock.MagicMock
        return KerasAssignment(
            name="Mock Exercise 1",
            identifier="12",
            validation_data=ValidationData.from_numpy(
                validation_data, validation_label
            ),
            validation_set_size=len(validation_data),
            input_selection_strategy=RandomSelectionStrategy(seed=20),
            submission_deadline=datetime.datetime(
                year=2019, month=12, day=31, hour=23, minute=59
            ),
        )


def test_raise_error_on_wrong_input_count(mock_assignment1: KerasAssignment) -> None:
    with unittest.mock.patch(
        "kerasltiprovider.utils.Datetime.now", spec=Datetime
    ) as mocked_time:
        mocked_time.return_value = datetime.datetime(
            year=2001, month=1, day=1, hour=0, minute=3
        )
        with pytest.raises(SubmissionValidationError):
            mock_assignment1.validate(dict())


def test_grade_calculation() -> None:
    with mock_redis_connection() as (_, __):
        # Mock inputs and predictions (3x3) images
        mock_input_matrices = [
            to_matrix([1, 2, 3], [4, 5, 6]),
            to_matrix([7, 8, 9], [10, 11, 12]),
            to_matrix([13, 14, 15], [16, 17, 18]),
            to_matrix([19, 20, 21], [22, 23, 24]),
        ]
        hashed_mock_input_matrices = {hash_matrix(i): i for i in mock_input_matrices}
        mock_inputs = np.array(list(hashed_mock_input_matrices.values()))
        mock_input_hashes = list(hashed_mock_input_matrices.keys())

        mock_predictions_correct = {
            mock_input_hashes[0]: 0,
            mock_input_hashes[1]: 0,
            mock_input_hashes[2]: 0,
            mock_input_hashes[3]: 0,
        }

        mock_predictions_okay = {
            mock_input_hashes[0]: 1,  # wrong
            mock_input_hashes[1]: 0,
            mock_input_hashes[2]: 0,
            mock_input_hashes[3]: 0,
        }

        mock_predictions_bad = {
            mock_input_hashes[0]: 1,  # wrong
            mock_input_hashes[1]: 1,  # wrong
            mock_input_hashes[2]: 0,
            mock_input_hashes[3]: 0,
        }

        mock_predictions_very_bad = {
            mock_input_hashes[0]: 1,  # wrong
            mock_input_hashes[1]: 1,  # wrong
            mock_input_hashes[2]: 1,  # wrong
            mock_input_hashes[3]: 1,  # wrong
        }

        validation_data = ValidationData.from_numpy(
            mock_inputs, np.array(np.array([0] * len(mock_input_matrices)))
        )

        assert [hash_matrix(m) for m in mock_inputs] == mock_input_hashes

        mock_assignment = KerasAssignment(
            name="Mock Exercise 1",
            identifier="0",
            validation_data=validation_data,
            validation_set_size=len(hashed_mock_input_matrices.values()),
            input_selection_strategy=RandomSelectionStrategy(seed=20),
            submission_deadline=datetime.datetime(
                year=2019, month=12, day=31, hour=23, minute=59
            ),
        )

        mock_assignment.save_validation_hash_table()

        with unittest.mock.patch(
            "kerasltiprovider.utils.Datetime.now", spec=Datetime
        ) as mocked_time:
            mocked_time.return_value = datetime.datetime(
                year=2001, month=1, day=1, hour=0, minute=3
            )
            assert mock_assignment.validate(mock_predictions_correct) == (1.0, 1.0)
            assert mock_assignment.validate(mock_predictions_okay) == (0.75, 0.75)
            assert mock_assignment.validate(mock_predictions_bad) == (0.5, 0.5)
            assert mock_assignment.validate(mock_predictions_very_bad) == (0, 0)


def test_accuracy_interpolation() -> None:
    assert interpolate_accuracy(acc=0.0, min=0.0, max=1.0) == 0.0
    assert interpolate_accuracy(acc=1.0, min=0.0, max=1.0) == 1.0
    assert interpolate_accuracy(acc=0.5, min=0.0, max=1.0) == 0.5

    assert interpolate_accuracy(acc=0.5, min=0.25, max=0.75) == 0.5
    assert interpolate_accuracy(acc=0.25, min=0.25, max=0.75) == 0.0
    assert interpolate_accuracy(acc=0.2, min=0.25, max=0.75) == 0.0
    assert interpolate_accuracy(acc=0.9, min=0.25, max=0.75) == 1.0
    assert interpolate_accuracy(acc=0.75, min=0.25, max=0.75) == 1.0
    assert interpolate_accuracy(acc=0.4, min=0.0, max=0.8) == 0.5
    assert (
        abs(
            round(interpolate_accuracy(acc=0.7, min=0.0, max=0.8), ndigits=2)
            - round(7.0 / 8.0, ndigits=2)
        )
        <= 0.02
    )
    assert (
        abs(
            round(interpolate_accuracy(acc=0.85, min=0.8, max=0.9), ndigits=2)
            - round(0.5, ndigits=2)
        )
        <= 0.02
    )


def test_checks_deadline(mock_assignment1: KerasAssignment) -> None:
    # Worst case
    with pytest.raises(SubmissionAfterDeadlineException):
        with pytest.raises(SubmissionValidationError):
            with unittest.mock.patch(
                "kerasltiprovider.utils.Datetime.now", spec=Datetime
            ) as mocked_time:
                mocked_time.return_value = datetime.datetime(
                    year=2020, month=1, day=1, hour=0, minute=3
                )
                mock_assignment1.validate(dict())

    # Average case (no SubmissionAfterDeadlineException exception)
    with pytest.raises(SubmissionValidationError):
        with unittest.mock.patch(
            "kerasltiprovider.utils.Datetime.now", spec=Datetime
        ) as mocked_time:
            mocked_time.return_value = datetime.datetime(
                year=2019, month=12, day=31, hour=23, minute=59
            )
            mock_assignment1.validate(dict())

    # Best case (no SubmissionAfterDeadlineException exception)
    with pytest.raises(SubmissionValidationError):
        with unittest.mock.patch(
            "kerasltiprovider.utils.Datetime.now", spec=Datetime
        ) as mocked_time:
            mocked_time.return_value = datetime.datetime(
                year=2019, month=12, day=31, hour=23, minute=30
            )
            mock_assignment1.validate(dict())
