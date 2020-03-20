import typing

import redis


class Database:

    assignments: typing.Optional[redis.Redis] = None
    users: typing.Optional[redis.Redis] = None

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379) -> None:
        self.redis_host = redis_host
        self.redis_port = redis_port

    def connect(self) -> None:
        self.__class__.users = redis.Redis(
            host=self.redis_host, port=self.redis_port, db=0, decode_responses=True
        )
        self.__class__.assignments = redis.Redis(
            host=self.redis_host, port=self.redis_port, db=1, decode_responses=True
        )
