import typing

from kerasltiprovider.types import AnyIDType


class KerasSubmissionRequest:
    def __init__(
        self, user: str, user_token: AnyIDType, assignment_id: AnyIDType
    ) -> None:
        self.user = user
        self.user_token = user_token
        self.assignment_id = assignment_id

    @property
    def formatted(self) -> typing.Dict[str, AnyIDType]:
        return dict(
            user=self.user, user_token=self.user_token, assignment_id=self.assignment_id
        )
