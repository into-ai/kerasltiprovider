import typing
from contextlib import contextmanager

import jaeger_client
import jaeger_client.metrics.prometheus as jaeger_metrics


class NoopScope:
    span: typing.Type["NoopScope"]

    @classmethod
    def set_tag(cls, *_args: typing.Any, **_kwargs: typing.Any) -> None:
        pass

    @classmethod
    def log_kv(cls, *_args: typing.Any, **_kwargs: typing.Any) -> None:
        pass


NoopScope.span = NoopScope


@contextmanager
def noop_span() -> typing.Iterator[typing.Type[NoopScope]]:
    yield NoopScope


class NoopTracer:
    @classmethod
    def start_span(
        cls, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Callable[..., typing.ContextManager[NoopScope]]:
        return noop_span()

    @classmethod
    def start_active_span(
        cls, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Callable[..., typing.ContextManager[NoopScope]]:
        return noop_span()


class Tracer:

    service_name: typing.Optional[str] = None
    tracer_host: typing.Optional[str] = None
    tracer_port: typing.Optional[int] = None

    config: typing.Optional[typing.Dict[str, typing.Any]] = None

    _tracer: typing.Optional[jaeger_client.Tracer] = None

    @classmethod
    def main(cls) -> jaeger_client.Tracer:
        return cls._tracer if cls._tracer else NoopTracer

    @classmethod
    def setup_tracer(
        cls,
        service_name: str = "kerasltiprovider",
        tracer_host: str = "localhost",
        tracer_port: int = 6831,
    ) -> None:
        cls.service_name = service_name
        cls.tracer_host = tracer_host
        cls.tracer_port = tracer_port

        cls.config = dict(sampler=dict(type="const", param=1), logging=True)

        if None not in (cls.tracer_host, cls.tracer_port):
            cls.config.update(
                dict(
                    local_agent=dict(
                        reporting_host=cls.tracer_host, reporting_port=cls.tracer_port
                    )
                )
            )

        jaeger = jaeger_client.Config(
            config=cls.config,
            service_name=cls.service_name,
            metrics_factory=jaeger_metrics.PrometheusMetricsFactory(
                namespace=cls.service_name
            ),
            validate=True,
        )

        cls._tracer = jaeger.initialize_tracer()
