
**Note**

The deployment files only serve for demonstration purposes and should not be used in production.

###### Usage

```bash
docker-compose \
    -f <example-configuration> \
    -f common/compose.tracing.yml \
    -f common/compose.redis.yml \
    up --build
```

or using the convenience script:

```bash
./<example-configuration>.sh up --build
```

This will build and start a local docker compose cluster including the `kerasltiprovider`, `redis` and 
`jaeger` utilities for tracing.

Substitute `<example-configuration>` with one of the included examples.