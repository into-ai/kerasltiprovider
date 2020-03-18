import typing

from kerasltiprovider.types import AnyIDType


class KerasSubmissionRequest:
    def __init__(
        self,
        user_id: str,
        user_token: AnyIDType,
        assignment_id: AnyIDType,
        params: typing.Dict[str, str],
    ) -> None:
        self.user_id = user_id
        self.user_token = user_token
        self.assignment_id = assignment_id
        self.params = params

    @property
    def formatted(self) -> typing.Dict[str, typing.Any]:
        return dict(
            user_id=self.user_id,
            user_token=self.user_token,
            assignment_id=self.assignment_id,
            params=self.params,
        )
