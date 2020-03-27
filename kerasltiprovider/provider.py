import datetime
import logging

import numpy as np
import pylti
import tensorflow as tf
from flask import Blueprint, current_app, jsonify, render_template, url_for
from lti import ToolConsumer
from pylti.flask import lti

from kerasltiprovider import context
from kerasltiprovider.assignment import find_assignment
from kerasltiprovider.exceptions import (
    ConfigurationErrorException,
    InvalidValidationHashTableException,
    PostingGradeFailedException,
    UnknownAssignmentException,
)
from kerasltiprovider.interceptors import (
    error_handler,
    get_or_create_user,
    on_error,
    restore_session,
    start_error_handler,
)
from kerasltiprovider.tracer import Tracer
from kerasltiprovider.types import AnyIDType, RequestResultType
from kerasltiprovider.utils import MIME, slash_join

mod = Blueprint("provider", __name__)

log = logging.getLogger("kerasltiprovider")
log.addHandler(logging.NullHandler())


@mod.route("/assignments", methods=["POST", "GET"])
@on_error(handler=error_handler)
def assignments() -> RequestResultType:
    """
    access route with 'initial' request only, subsequent requests are not allowed.

    :param: lti: `lti` object
    :return: string "Initial request"
    """
    assignments = [
        dict(
            identifier=a.identifier,
            description=a.name,
            validation_set_size=a.validation_set_size,
            partial_loading=a.partial_loading,
        )
        for a in context.assignments
    ]
    return jsonify(dict(assignments=assignments)), 200, MIME.json


@mod.route("/assignment/<assignment_id>/inputs", methods=["POST", "GET"])
@on_error(handler=error_handler)
def inputs(assignment_id: AnyIDType) -> RequestResultType:
    """
    access route with 'initial' request only, subsequent requests are not allowed.

    :param: lti: `lti` object
    :return: string "Initial request"
    """
    with Tracer.main().start_span("assignment_inputs") as span:
        span.set_tag("assignment_id", assignment_id)

        try:
            assignment = find_assignment(assignment_id)
        except (TypeError, ValueError, IndexError):
            log.warning(
                f"Ingoring request of validation inputs for unknown assignment: {assignment_id}"
            )
            raise UnknownAssignmentException(
                "Unknown assignment", assignment_id=assignment_id, status=404
            )

        span.log_kv(dict(assignment=assignment.formatted))

        if assignment.partial_loading:
            return (
                jsonify(
                    dict(error="Inputs need to be loaded individually", success=False)
                ),
                404,
                MIME.json,
            )

        inputs = []
        for mhash, req in assignment.validation_hash_table.items():
            _matrix: tf.Tensor = req["matrix"]
            matrix = _matrix.numpy()
            if not isinstance(matrix, np.ndarray):
                raise InvalidValidationHashTableException(
                    "Validation hash table contains key without prediction",
                    assignment_id=assignment_id,
                )
            inputs.append(dict(matrix=matrix.tolist(), hash=mhash))
        span.log_kv(dict(predict=inputs))
        return jsonify(dict(predict=inputs)), 200, MIME.json


@mod.route("/assignment/<assignment_id>/inputs/<input_id>", methods=["POST", "GET"])
@on_error(handler=error_handler)
def inputs_single(assignment_id: AnyIDType, input_id: int) -> RequestResultType:
    """
    access route with 'initial' request only, subsequent requests are not allowed.

    :param: lti: `lti` object
    :return: string "Initial request"
    """
    with Tracer.main().start_span("assignment_inputs") as span:
        span.set_tag("assignment_id", assignment_id)

        try:
            assignment = find_assignment(assignment_id)
        except (TypeError, ValueError, IndexError):
            log.warning(
                f"Ingoring request of validation inputs for unknown assignment: {assignment_id}"
            )
            raise UnknownAssignmentException(
                "Unknown assignment", assignment_id=assignment_id, status=404
            )

        span.log_kv(dict(assignment=assignment.formatted))

        try:
            input_id = int(input_id)
        except ValueError:
            return (
                jsonify(dict(error="Input_id needs to be an integer", success=False)),
                404,
                MIME.json,
            )

        if input_id >= len(assignment.validation_hash_table.items()):
            return (
                jsonify(dict(error="You exceeded the number of Inputs", success=False)),
                404,
                MIME.json,
            )

        inputs = []
        mhash, req = list(assignment.validation_hash_table.items())[input_id]
        _matrix: tf.Tensor = req["matrix"]
        matrix = _matrix.numpy()
        if not isinstance(matrix, np.ndarray):
            raise InvalidValidationHashTableException(
                "Validation hash table contains key without prediction",
                assignment_id=assignment_id,
            )
        inputs.append(dict(matrix=matrix.tolist(), hash=mhash))
        span.log_kv(dict(predict=inputs))
        return jsonify(dict(predict=inputs)), 200, MIME.json


@mod.route("/start", methods=["POST", "GET"])
@lti(error=start_error_handler, request="initial", app=current_app)
@on_error(handler=start_error_handler)
def start(lti: pylti.flask.LTI) -> RequestResultType:
    """
    access route with 'initial' request only, subsequent requests are not allowed.

    :param: lti: `lti` object
    :return: string "Initial request"
    """
    with Tracer.main().start_span("start") as span:
        with get_or_create_user(lti, span) as lti_request:
            assignment = find_assignment(lti_request.assignment_id)
            public_url = current_app.config.get("PUBLIC_URL")
            base_url = url_for("provider.health")
            if None in [public_url, base_url]:
                raise ConfigurationErrorException(
                    f"Cannot create inputs endpoint from PUBLIC_URL={public_url} and PATH={base_url}"
                )
            input_api_endpoint = slash_join(str(public_url), str(base_url))
            if (
                str(current_app.config.get("ENABLE_ABSOLUTE_INPUT_ENDPOINT_URL"))
                == "true"
            ):
                input_api_endpoint = slash_join(
                    input_api_endpoint,
                    url_for("provider.inputs", assignment_id=assignment.identifier),
                )
            submission_url = url_for("provider.submit")
            if None in [public_url, submission_url]:
                raise ConfigurationErrorException(
                    f"Cannot create submission endpoint from PUBLIC_URL={public_url} and PATH={submission_url}"
                )
            submission_api_endpoint = slash_join(str(public_url), str(submission_url))
            template_options = dict(
                lti_request=lti_request,
                user_id=lti_request.user_id,
                user_token=lti_request.user_token,
                assignment_name=assignment.name,
                assignment_id=assignment.identifier,
                logo_uri=current_app.config.get("PROVIDER_LOGO_URI"),
                input_api_endpoint=input_api_endpoint,
                submission_api_endpoint=submission_api_endpoint,
                now=datetime.datetime.utcnow(),
                provider_name=current_app.config.get("PROVIDER_NAME"),
            )

            code = render_template(
                current_app.config.get("TEMPLATE_PREFIX", "") + "code.jinja2",
                **template_options,
            )
            template_options["code_snippet"] = code
            span.log_kv(template_options)
            return (
                render_template(
                    current_app.config.get("TEMPLATE_PREFIX", "") + "start.html",
                    **template_options,
                ),
                200,
                MIME.html,
            )


@mod.route("/submit", methods=["POST"])
@on_error(handler=error_handler)
@restore_session
@lti(request="session", error=error_handler, app=current_app)
def submit(
    grade: float,
    accuracy: float,
    user_token: str,
    assignment_id: str,
    lti: pylti.flask.LTI,
) -> RequestResultType:
    """ post grade
    :return: grade rendered by grade.html template
    """
    with Tracer.main().start_span("grading_submission") as span:
        span.set_tag("grade_percent", grade)
        span.log_kv(
            dict(
                grade=grade,
                accuracy=accuracy,
                user_token=user_token,
                user_id=lti.user_id,
                assignment_id=assignment_id,
            )
        )

        from pylti.common import LTI_PROPERTY_LIST, LTI_SESSION_KEY

        ltisession = {
            prop: lti.session.get(prop, None)
            for prop in LTI_PROPERTY_LIST + [LTI_SESSION_KEY]
        }
        log.debug(f"Session: {ltisession}")

        try:
            log.info(
                f"Submitting grade {grade} for user {lti.user_id} assignment {assignment_id} to {lti.response_url}"
            )
            lti.post_grade(grade)
        except Exception as e:
            log.error(e)
            raise PostingGradeFailedException(
                "Failed to submit the grade to the LTI Consumer",
                user_id=lti.user_id,
                assignment_id=assignment_id,
            )
        return (
            jsonify(
                dict(
                    grade=grade,
                    accuracy=accuracy,
                    message=f"Successfully graded for {assignment_id}: Received {grade*100}% (acc={accuracy})",
                )
            ),
            200,
            MIME.json,
        )


@mod.route("/")
def health() -> RequestResultType:
    return jsonify(dict(healthy=True)), 200, MIME.json


@mod.route("/launch", methods=["POST", "GET"])
def launch() -> RequestResultType:
    if (
        str(current_app.config.get("ENABLE_DEBUG_LAUNCHER")).lower() == "true"
        and str(current_app.config.get("PRODUCTION")).lower() == "false"
    ):
        public_url = current_app.config.get("PUBLIC_URL")
        url = url_for("provider.start")
        if None in [public_url, url]:
            raise ConfigurationErrorException(
                f"Cannot create launch URL from PUBLIC_URL={public_url} and PATH={url}"
            )
        params = dict(
            lti_message_type="basic-lti-launch-request",
            lti_version="lti_version",
            resource_link_id=2,
            context_id="Open HPI",
            user_id="max",
            roles=["student"],
            context_title="Open HPI Mooc Neural Networks 2019",
            context_label="Open HPI NN 2019",
            lis_person_name_full="Max Mustermann",
            lis_outcome_service_url="http://localhost:8080/savegrade",
        )

        # Custom args MUST start with custom_
        params[
            current_app.config.get("LAUNCH_ASSIGNMENT_ID_PARAM")
            or "custom_x-assignment-id"
        ] = 2
        consumer = ToolConsumer(
            consumer_key=current_app.config.get("CONSUMER_KEY"),
            consumer_secret=current_app.config.get("CONSUMER_KEY_SECRET"),
            launch_url=slash_join(str(public_url), str(url)),
            params=params,
        )
        return (
            render_template(
                current_app.config.get("TEMPLATE_PREFIX", "") + "launch.html",
                launch_data=consumer.generate_launch_data(),
                launch_url=consumer.launch_url,
            ),
            200,
            MIME.html,
        )
    else:
        return jsonify(dict(error="The launcher is disabled")), 200, MIME.json
