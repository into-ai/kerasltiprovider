import typing

from kerasltiprovider.utils import MIMEType

AnyIDType = str  # used to be typing.Union[str, int] but lti will most certainly fall back to strings
RequestResultType = typing.Tuple[str, int, MIMEType]
