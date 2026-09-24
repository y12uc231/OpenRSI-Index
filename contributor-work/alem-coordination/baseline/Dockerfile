FROM python:3.12-slim@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JAX_PLATFORM_NAME=cpu WANDB_MODE=disabled
COPY requirements.lock /build/requirements.lock
# Exact versions observed in the successful CPU image. No GPU dependencies.
RUN python -m pip install --no-cache-dir --no-deps -r /build/requirements.lock
WORKDIR /app
COPY source/pyproject.toml source/README.md source/LICENSE ./
COPY source/alem ./alem
# setuptools supplies its wheel command; no dependency re-resolution here.
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation -e .
WORKDIR /tmp
