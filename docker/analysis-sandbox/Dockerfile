FROM python:3.12-slim

RUN useradd --create-home --uid 65532 appuser \
    && pip install --no-cache-dir pandas numpy matplotlib

USER 65532:65532
WORKDIR /workspace
