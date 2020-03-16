import datetime
import functools
import json
import logging
import traceback
import typing
import uuid
from contextlib import contextmanager

import jaeger_client.span
import pylti
from flask import jsonify, request, session
from pylti.common import LTI_PROPERTY_LIST, LTI_SESSION_KEY

from kerasltiprovider.assignment import find_assignment
from kerasltiprovider.database import Database
from kerasltiprovider.exceptions import (
    KerasLTIProviderException,
    NoDatabaseException,
    UnknownUserTokenException,
)
from kerasltiprovider.submission import KerasSubmissionRequest
from kerasltiprovider.tracer import Tracer
from kerasltiprovider.types import RequestResultType
from kerasltiprovider.utils import MIME, MIMEType

log = logging.getLogger("kerasltiprovider")
log.addHandler(logging.NullHandler())

ErrType = typing.Dict[str, typing.Any]
ErrResultType = typing.Tuple[str, int, MIMEType]


def error_handler(_exception: typing.Optional[ErrType] = None) -> RequestResultType:
    """ render error page
    :param exception: optional exception
    :return: the error.html template rendered
    """
    with Tracer.main().start_active_span("error_handler") as scope:
        exception = _exception or dict()
        exc = exception.get("exception", Exception)
        status_code = getattr(exc, "status", 500)
        message = "The requested operation could not be completed"
        user_id = None

        scope.span.log_kv(dict(exception=exception, exc=exc, status_code=status_code,))

        # More detailed error messages for LTI issues
        if isinstance(exc, pylti.common.LTINotInSessionException):
            log.info("Ignoring request from user with invalid session")
            message = "LTI invalid session"
        elif isinstance(exc, pylti.common.LTIException):
            log.warning("LTI error")
            message = str(exc)

        # We can pass our custom error messages
        elif isinstance(exc, KerasLTIProviderException):
            log.error(exc)
            user_id = exc.user_id
            message = str(exc)

        # Use default error message on unknown errors
        else:
            # raise exc
            log.error(exc)

        scope.span.log_kv(dict(message=message))

        response = dict(error=message, success=False)
        if user_id is not None:
            response["user_id"] = user_id

        print("Returning %s" % response)
        return jsonify(response), status_code, MIME.json


def on_error(
    handler: typing.Callable[[ErrType], ErrResultType]
) -> typing.Callable[[typing.Callable[..., typing.Any]], typing.Any]:
    def decorator(
        func: typing.Callable[..., typing.Any]
    ) -> typing.Callable[..., typing.Any]:
        @functools.wraps(func)
        def catch_exceptions(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return handler(dict(exception=e))

        return catch_exceptions

    return decorator


def restore_session(
    func: typing.Callable[..., typing.Any]
) -> typing.Callable[..., typing.Any]:
    with Tracer.main().start_active_span("restore_session") as scope:
        scope.span.set_tag("func", func)

        @functools.wraps(func)
        def decorator(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            scope.span.log_kv(kwargs)
            restored_session = dict()
            try:
                data = request.get_json()
                predictions = data["predictions"]
                user_token = data["user_token"]
                assignment_id = data["assignment_id"]
                assignment = find_assignment(assignment_id)

                if not Database.users:
                    raise NoDatabaseException
                user = Database.users.get("session:" + user_token)
                if not user:
                    raise UnknownUserTokenException(
                        f"The token {user_token} is not a valid token. Relaunch to obtain a valid token!"
                    )
                restored_session = json.loads(
                    Database.users.get("session:" + user_token)
                )
                for k, v in restored_session.items():
                    session[k] = v
                score = assignment.validate(predictions)

                scope.span.log_kv(
                    dict(
                        predictions=predictions,
                        user_token=user_token,
                        assignment_id=assignment_id,
                        assignment=assignment,
                        restored_session=restored_session,
                        session=session,
                        score=score,
                    )
                )

                return func(grade=score, *args, **kwargs)

            except KerasLTIProviderException as e:
                e.user_id = restored_session.get("user_id")
                e.assignment_id = restored_session.get("assignment_id")
                raise e

            except Exception:
                traceback.print_exc()
                raise

        return decorator


@contextmanager
def get_or_create_user(
    _lti: pylti.flask.LTI, span: jaeger_client.span.Span
) -> typing.Iterator[KerasSubmissionRequest]:
    assert _lti.verify()
    user_id = _lti.user_id
    resource_link_id = _lti.session.get("resource_link_id", None)
    session = json.dumps(
        {
            prop: _lti.session.get(prop, None)
            for prop in LTI_PROPERTY_LIST + [LTI_SESSION_KEY]
        }
    )
    user_token = str(uuid.uuid4())

    span.set_tag("user_id", user_id)
    span.set_tag("resource_link_id", resource_link_id)
    span.set_tag("user_token", user_token)

    span.log_kv(dict(session=session))

    if not Database.users:
        raise NoDatabaseException
    Database.users.setex(user_id, datetime.timedelta(hours=48), user_token)
    Database.users.setex("session:" + user_token, datetime.timedelta(hours=48), session)
    yield KerasSubmissionRequest(
        user=user_id, user_token=user_token, assignment_id=resource_link_id
    )
