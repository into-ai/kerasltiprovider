import os
import pathlib
import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from kerasltiprovider.assignment import KerasAssignment  # noqa: F401

"""
Configuration file for the Keras LTI Provider
"""

wd = os.path.dirname(os.path.realpath(__file__))

# Assignments to validate and provide inputs for
# This might be overridden with a user level config
ASSIGNMENTS: typing.List["KerasAssignment"] = []

# Redis config connection
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)

# Jaeger tracer connection
JAEGER_HOST = os.environ.get("JAEGER_HOST", "localhost")
JAEGER_PORT = os.environ.get("JAEGER_PORT", 6831)

# Service config
PORT = os.environ.get("PORT", 3000)
HOST = os.environ.get("HOST", "0.0.0.0")

# Path to register the blueprint under
# This does not make sense with env vars but when
URL_PREFIX = os.environ.get("URL_PREFIX") or "/"

# Where the service will be running at in production
PUBLIC_PORT = os.environ.get("PUBLIC_PORT") or PORT
PUBLIC_HOST = os.environ.get("PUBLIC_HOST") or HOST
PUBLIC_PATH = os.environ.get("PUBLIC_PATH") or URL_PREFIX

# Enable or disable production mode
PRODUCTION = os.environ.get("PRODUCTION", "True")

# ENABLE_ABSOLUTE_INPUT_ENDPOINT_URL
ENABLE_ABSOLUTE_INPUT_ENDPOINT_URL = os.environ.get(
    "ENABLE_ABSOLUTE_INPUT_ENDPOINT_URL", "False"
)

# Location where to look for template files
TEMPLATE_DIR = os.environ.get("TEMPLATE_DIR") or pathlib.Path(wd) / pathlib.Path(
    "templates"
)

# Prefix to append before the template files
TEMPLATE_PREFIX = os.environ.get("TEMPLATE_PREFIX", "")

#
# LTI Related
#

# Custom argument storing the assignment ID
LAUNCH_ASSIGNMENT_ID_PARAM = os.environ.get(
    "LAUNCH_ASSIGNMENT_ID_PARAM", "custom_x-assignment-id"
)

USER_TOKEN_EXPIRE_HOURS = os.environ.get("USER_TOKEN_EXPIRE_HOURS") or 48
ENABLE_TOKEN_FROM_USER_ID = os.environ.get("ENABLE_TOKEN_FROM_USER_ID", "False")

# Flask secret key for secure session management
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("No FLASK_SECRET_KEY set for flask application")

# Name of this provider (e.g. institution)
PROVIDER_NAME = os.environ.get("PROVIDER_NAME", "KerasLTIProvider")

# URI of the providers logo to be rendered in templates
PROVIDER_LOGO_URI = os.environ.get("PROVIDER_LOGO_URI")

# Name of the accepted tool consumer
CONSUMER_NAME = os.environ.get("CONSUMER_NAME")

# Name of the accepted tool consumer
CONSUMER_KEY = os.environ.get("CONSUMER_KEY", "consumer")

# PEM file containing the consumers secret key
CONSUMER_KEY_PEM_FILE = (
    pathlib.Path(wd) / pathlib.Path("certs/ca-key.pem")
    if not os.environ.get("CONSUMER_KEY_PEM_FILE")
    else pathlib.Path(str(os.environ.get("CONSUMER_KEY_PEM_FILE")))
)

# Consumers secret key with higher precedence
CONSUMER_KEY_SECRET = os.environ.get("CONSUMER_KEY_SECRET")

# Check if either secret or PEM file were provided
if not (CONSUMER_KEY_PEM_FILE.is_file() or CONSUMER_KEY_SECRET is not None):
    raise ValueError("Missing CONSUMER_KEY_SECRET")

# Write consumer secret to cert file
try:
    CONSUMER_KEY_PEM_FILE.parent.mkdir()
except FileExistsError:
    pass
if CONSUMER_KEY_SECRET:
    with open(CONSUMER_KEY_PEM_FILE, "w+") as pem_file:
        pem_file.write(CONSUMER_KEY_SECRET)

# Config used by the pylti flask plugin
# This might be overridden with a user level config
PYLTI_CONFIG = dict(
    consumers={
        CONSUMER_KEY: dict(secret=CONSUMER_KEY_SECRET)
        # cert=CONSUMER_KEY_PEM_FILE)
    }
)

#
# Debug related
#

# Set the log level
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Whether the input data database should not be reset upon restarts
KEEP_ASSIGNMENTS_DATABASE = os.environ.get("KEEP_ASSIGNMENTS_DATABASE", "False")

# Whether a debug LTI consumer should provide a launch at /launch
ENABLE_DEBUG_LAUNCHER = os.environ.get("ENABLE_DEBUG_LAUNCHER", "False")

#
# Inferred values
#

SAFE_PUBLIC_PATH = "/".join([c for c in PUBLIC_PATH.split("/") if len(c) > 0])
PUBLIC_URL = (
    os.environ.get("PUBLIC_URL")
    or f"http://{PUBLIC_HOST}:{PUBLIC_PORT}{SAFE_PUBLIC_PATH}"
)
