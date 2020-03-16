import typing

from kerasltiprovider.utils import MIMEType

AnyIDType = typing.Union[str, int]
RequestResultType = typing.Tuple[str, int, MIMEType]
