# -*- coding: utf-8 -*-

"""Main module."""

import os
import typing

from flask import Blueprint, Flask
from waitress import serve

from kerasltiprovider import config as default_config
from kerasltiprovider import context
from kerasltiprovider.assignment import KerasAssignment
from kerasltiprovider.database import Database
from kerasltiprovider.exceptions import MissingAssignmentsException
from kerasltiprovider.tracer import Tracer

KLTIPType = typing.TypeVar("KLTIPType", bound="KerasLTIProvider")
ConfigType = typing.Dict[str, typing.Any]
LTIConfigType = typing.Dict[str, typing.Any]


class KerasLTIProvider:
    def __init__(
        self,
        app: Flask,
        assignments: typing.Optional[typing.List[KerasAssignment]] = None,
        lti_config: typing.Optional[LTIConfigType] = None,
        config: typing.Optional[ConfigType] = None,
    ):
        """Create or use an existing app"""
        self.app = app
        self.load_config(config, lti_config)
        self.check_assignments(assignments)
        self.connect_tracer()
        self.connect_redis()

        # Insert assignment inputs into redis database
        if not self.app.config.get("KEEP_DATABASE"):
            self.app.logger.info("Flushing assignments")
            if Database.assignments:
                Database.assignments.flushdb()
            self.app.logger.info("Creating validation hash table for assignments")
            for a in context.assignments:
                a.save_validation_hash_table()

    @classmethod
    def create(
        cls: typing.Type[KLTIPType],
        assignments: typing.Optional[typing.List[KerasAssignment]] = None,
        lti_config: typing.Optional[LTIConfigType] = None,
        config: typing.Optional[ConfigType] = None,
    ) -> KLTIPType:
        app = Flask(__name__)
        provider = cls(app, assignments, lti_config, config)

        provider.register_blueprint()
        return provider

    def register_blueprint(self) -> None:
        # Register the blueprint
        base_path = self.app.config.get("BLUEPRINT_PATH") or "/"

        self.app.register_blueprint(self.blueprint(), url_prefix=base_path)

    def check_assignments(
        self, assignments: typing.Optional[typing.List[KerasAssignment]]
    ) -> None:
        # Check for assignments
        context.assignments = assignments or self.app.config.get("ASSIGNMENTS") or []
        if len(context.assignments) < 1:
            raise MissingAssignmentsException(
                "Cannot start without at least one assignment"
            )

    def load_config(
        self,
        config: typing.Optional[ConfigType],
        lti_config: typing.Optional[LTIConfigType],
    ) -> None:
        # Load default config
        self.app.config.from_object(default_config.__name__)

        assignments_config = os.environ.get("ASSIGNMENTS_PY_CONFIG", None)
        if assignments_config is not None:
            # Override config with user defined config
            self.app.config.from_pyfile(assignments_config)

        user_config = os.environ.get("USER_PY_CONFIG", None)
        if user_config is not None:
            # Override config with user defined config
            self.app.config.from_pyfile(user_config)

        # Local configuration takes precedence
        if config is not None:
            # Override config with local user defined config
            self.app.config.update(**config)

        if lti_config is not None:
            # Override config with local user defined lti_config
            self.app.config.update(**lti_config)

    def connect_tracer(self) -> None:
        # Connect the tracer
        jaeger_host = self.app.config.get("JAEGER_HOST", "localhost")
        jaeger_port = self.app.config.get("JAEGER_PORT", 6831)

        try:
            Tracer.setup_tracer(tracer_host=jaeger_host, tracer_port=jaeger_port)
        except Exception as e:
            self.app.logger.error(f"Failed to setup the tracer: {str(e)}")

    def connect_redis(self) -> None:
        # Connect the redis database
        redis_host = self.app.config.get("REDIS_HOST", "localhost")
        redis_port = self.app.config.get("REDIS_PORT", 6379)

        # Connect the redis database
        Database(redis_host=redis_host, redis_port=redis_port).connect()

    def blueprint(self) -> Blueprint:
        from kerasltiprovider import provider

        # Set the template directory
        if self.app.config.get("TEMPLATE_DIR"):
            provider.mod.template_folder = self.app.config.get("TEMPLATE_DIR")
        return provider.mod

    def run(self) -> None:
        host = self.app.config.get("HOST") or "0.0.0.0"
        port = self.app.config.get("PORT") or 3000
        serve(self.app, host=host, port=port)
