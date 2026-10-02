# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --upgrade pip build \
    && python -m build --wheel --outdir /wheels


FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime

LABEL org.opencontainers.image.title="OmniScrape" \
      org.opencontainers.image.description="Secure, deterministic web content extraction API" \
      org.opencontainers.image.source="https://github.com/Z-MarkUs/OmniScrape" \
      org.opencontainers.image.licenses="MIT"

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system --gid 10001 omniscrape \
    && adduser --system --uid 10001 --ingroup omniscrape --home /nonexistent --no-create-home omniscrape

COPY --from=builder /wheels /wheels
RUN python -m pip install /wheels/*.whl \
    && rm -rf /wheels

USER 10001:10001
WORKDIR /app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()"]

CMD ["omniscrape", "serve", "--host", "0.0.0.0", "--port", "8000"]
