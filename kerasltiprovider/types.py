import typing

from kerasltiprovider.utils import MIMEType

AnyIDType = str  # used to be typing.Union[str, int] but lti will most certainly fall back to strings
RequestResultType = typing.Tuple[str, int, MIMEType]

ValHTType = typing.Dict[str, typing.Dict[str, str]]
PredType = typing.Dict[str, int]


class KerasBaseAssignment:
    def __init__(self, identifier: AnyIDType):
        self.identifier = identifier

    def input_key_for(self, matrix_hash: str) -> str:
        return f"{self.identifier}:{matrix_hash}"
