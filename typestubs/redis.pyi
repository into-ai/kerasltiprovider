from typing import Text, Any, Union, Optional, Iterator, List
import datetime

class Redis(object):
    """Type stubs for redis"""
    def __init__(
        self,
        host: Text = ...,
        port: int = ...,
        db: int = ...,
        decode_responses: bool = ...,
    ) -> None: ...
    def hget(self, name: Union[Text, bytes], key: Union[Text, bytes]) -> Any: ...
    def hmget(self, name: Union[Text, bytes], *keys: Union[Text, bytes]) -> List[Any]: ...
    def flushdb(self) -> bool: ...
    def setex(self, name: Union[Text, bytes], time: datetime.timedelta, value: Union[Text, bytes]) -> Any: ...
    def get(self, name: Union[Text, bytes]) -> Any: ...
    def pipeline(self, transaction: Any =..., shard_hint: Any=...) -> Any: ...
    def scan_iter(self, match: Optional[Text] = ..., count: Optional[int] = ...) -> Iterator[Any]: ...

