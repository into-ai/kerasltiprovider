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
from flask import current_app, jsonify, render_template
from flask import request as flask_request
from flask import session
from pylti.common import LTI_PROPERTY_LIST, LTI_SESSION_KEY

from kerasltiprovider.assignment import find_assignment
from kerasltiprovider.database import Database
from kerasltiprovider.exceptions import (
    KerasLTIProviderException,
    MissingAssignmentIDException,
    NoDatabaseException,
    UnknownAssignmentException,
    UnknownUserTokenException,
)
from kerasltiprovider.submission import KerasSubmissionRequest
from kerasltiprovider.tracer import Tracer
from kerasltiprovider.types import RequestResultType
from kerasltiprovider.utils import MIME, MIMEType, get_session_id, hash_user_id

log = logging.getLogger("kerasltiprovider")
log.addHandler(logging.NullHandler())

ErrType = typing.Dict[str, typing.Any]
ErrResultType = typing.Tuple[str, int, MIMEType]


def start_error_handler(
    exception: typing.Optional[ErrType] = None,
) -> RequestResultType:
    _exception = exception or dict()
    exc = _exception.get("exception", Exception)
    status_code = getattr(exc, "status", 500)
    log.warning(str(exc))
    return (
        render_template(
            current_app.config.get("TEMPLATE_PREFIX", "") + "error.html",
            error=str(exc),
            now=datetime.datetime.utcnow(),
            provider_name=current_app.config.get("PROVIDER_NAME"),
            consumer_name=current_app.config.get("CONSUMER_NAME"),
        ),
        status_code,
        MIME.html,
    )


def error_handler(exception: typing.Optional[ErrType] = None) -> RequestResultType:
    with Tracer.main().start_active_span("error_handler") as scope:
        _exception = exception or dict()
        exc = _exception.get("exception", Exception)
        status_code = getattr(exc, "status", 500)
        message = "The requested operation could not be completed"
        user_id = None

        scope.span.log_kv(dict(exception=_exception, exc=exc, status_code=status_code,))
        log.error(str(exc))

        # We can pass our custom error messages
        if isinstance(exc, KerasLTIProviderException):
            user_id = exc.user_id
            message = str(exc)

        scope.span.log_kv(dict(message=message))

        response = dict(error=message, success=False)
        if user_id is not None:
            response.update(user_id=user_id)

        log.info(response)
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
                raise e
                return handler(dict(exception=e))

        return catch_exceptions

    return decorator


def restore_session(
    func: typing.Callable[..., typing.Any]
) -> typing.Callable[..., typing.Any]:
    with Tracer.main().start_active_span("restore_session") as scope:

        @functools.wraps(func)
        def decorator(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            scope.span.log_kv(kwargs)

            user_id = None
            assignment_id = None
            try:
                data = flask_request.get_json()
                predictions = data["predictions"]
                user_token = data["user_token"]
                assignment_id = data["assignment_id"]
                submission = dict(
                    num_predictions=len(predictions),
                    user_token=user_token,
                    assignment_id=assignment_id,
                )
                log.debug(f"Restoring session for submission [{str(submission)}]")

                assignment = find_assignment(assignment_id)
                if not assignment:
                    raise UnknownAssignmentException(
                        f"No assignment with id {assignment_id}"
                    )

                if not Database.users:
                    raise NoDatabaseException

                user = Database.users.get(get_session_id(assignment_id, user_token))

                if not user:
                    raise UnknownUserTokenException(
                        f"The token {user_token} is not valid or has expired. Try again with a new token!"
                    )

                restored_session = json.loads(user)
                for k, v in restored_session.items():
                    session[k] = v
                accuracy, score = assignment.validate(predictions)
                log.debug(f"accuracy={accuracy}, score={score}")

                scope.span.log_kv(
                    dict(
                        predictions=predictions,
                        user_token=user_token,
                        assignment_id=assignment_id,
                        assignment=assignment,
                        restored_session=restored_session,
                        session=session,
                        accuracy=accuracy,
                        score=score,
                    )
                )

                return func(
                    grade=score,
                    accuracy=accuracy,
                    user_token=user_token,
                    assignment_id=assignment_id,
                    *args,
                    **kwargs,
                )

            except KerasLTIProviderException as e:
                e.user_id = user_id
                e.assignment_id = assignment_id
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

    if flask_request.method == "POST":
        params = flask_request.form.to_dict()
    else:
        params = flask_request.args.to_dict()

    assignment_id_key = (
        current_app.config.get("LAUNCH_ASSIGNMENT_ID_PARAM") or "custom_x-assignment-id"
    )

    # Query the current session
    session = json.dumps(
        {
            prop: _lti.session.get(prop, None)
            for prop in LTI_PROPERTY_LIST + [LTI_SESSION_KEY]
        }
    )

    user_id = _lti.user_id
    assignment_id = params.get(assignment_id_key)

    if not assignment_id:
        raise MissingAssignmentIDException(
            f"Missing assignment id (expected at key {assignment_id_key})"
        )

    user_token = str(uuid.uuid4())
    if str(current_app.config.get("ENABLE_TOKEN_FROM_USER_ID")).lower() == "true":
        user_token = hash_user_id(user_id, assignment_id=assignment_id)

    span.set_tag("user_id", user_id)
    span.set_tag("assignment_id", assignment_id)
    span.set_tag("user_token", user_token)

    span.log_kv(
        dict(user_id=user_id, assignment_id=assignment_id, user_token=user_token)
    )

    if not Database.users:
        raise NoDatabaseException
    try:
        expire_hours = int(current_app.config.get("USER_TOKEN_EXPIRE_HOURS") or 4)
    except ValueError:
        log.warning(
            f"{current_app.config.get('USER_TOKEN_EXPIRE_HOURS')} is not a valid expiration time"
        )
        expire_hours = 4
    log.debug(
        f"Saving {get_session_id(assignment_id, user_token)} (expires in {expire_hours} hours)"
    )
    Database.users.setex(
        get_session_id(assignment_id, user_token),
        datetime.timedelta(hours=expire_hours),
        session,
    )
    yield KerasSubmissionRequest(
        user_id=user_id,
        user_token=user_token,
        assignment_id=assignment_id,
        params=params,
    )
