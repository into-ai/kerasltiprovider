import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from kerasltiprovider.assignment import KerasAssignment  # noqa: F401

assignments: typing.List["KerasAssignment"] = []
