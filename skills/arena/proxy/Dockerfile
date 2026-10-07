# Arena proxy backend: one small image, no build step, no secrets baked in.
FROM python:3.12-alpine

WORKDIR /app

# The package is standard-library only, so the source tree is the whole build.
COPY scripts/ /app/

RUN adduser -D -H extension && \
    mkdir -p /state && \
    chown extension /state

USER extension

ENV ARENA_PROXY_HOST=0.0.0.0 \
    ARENA_PROXY_PORT=8787 \
    ARENA_PROXY_STATE_DIR=/state

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/v1/health')"

CMD ["python", "-m", "arena_proxy"]
