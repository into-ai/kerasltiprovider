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

# Base path the service will be running at in production
BASE_PATH = os.environ.get("BASE_PATH", "/")

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

# Flask secret key for secure session management
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("No FLASK_SECRET_KEY set for flask application")

# Name of this provider (e.g. institution)
PROVIDER_NAME = os.environ.get("PROVIDER_NAME", "KerasLTIProvider")

# URI of the providers logo to be rendered in templates
PROVIDER_LOGO_URI = os.environ.get("PROVIDER_LOGO_URI")

# Name of the accepted tool consumer
CONSUMER_NAME = os.environ.get("CONSUMER_NAME", "consumer")

# PEM file containing the consumers secret key
CONSUMER_KEY_PEM_FILE = pathlib.Path(wd) / pathlib.Path("certs/ca-key.pem")

# Consumers secret key
CONSUMER_KEY_SECRET = os.environ.get("CONSUMER_KEY_SECRET", "123456")


# Might remove?
dirname = os.path.dirname(CONSUMER_KEY_PEM_FILE)
if not os.path.exists(dirname):
    os.makedirs(dirname)
with open(CONSUMER_KEY_PEM_FILE, "w+") as pem_file:
    pem_file.write(os.environ.get("CONSUMER_KEY_CERT", "123456"))

# Config used by the pylti flask plugin
# This might be overridden with a user level config
PYLTI_CONFIG = dict(
    consumers={
        CONSUMER_NAME: dict(secret=CONSUMER_KEY_SECRET, cert=CONSUMER_KEY_PEM_FILE)
    }
)

#
# Debug related
#

# Whether the input data database should not be reset upon restarts
KEEP_DATABASE = os.environ.get("KEEP_DATABASE", "False")

# Whether a debug LTI consumer should provide a launch at /launch
ENABLE_DEBUG_LAUNCHER = os.environ.get("ENABLE_DEBUG_LAUNCHER", "False")

#
# Inferred values
#

SAFE_BASE_PATH = "/".join([c for c in BASE_PATH.split("/") if len(c) > 0])
PUBLIC_URL = f"http://{HOST}:{PORT}{SAFE_BASE_PATH}"
