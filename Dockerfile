FROM python:3.12-slim

ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN arch=${TARGETARCH}; \
    [ "$arch" = "amd64" ] && arch="x86_64"; \
    [ "$arch" = "arm64" ] && arch="aarch64"; \
    curl -fsSL "https://download.docker.com/linux/static/stable/${arch}/docker-26.1.4.tgz" \
    | tar xz -C /usr/local/bin --strip-components=1 docker/docker

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

ARG VERSION
ENV APP_VERSION=${VERSION}
RUN test -n "$VERSION" && echo "$VERSION" > /app/VERSION 2>/dev/null || true

ARG DOCKER_HASH
RUN test -n "$DOCKER_HASH" && echo "$DOCKER_HASH" > /app/DOCKER_HASH 2>/dev/null || true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
