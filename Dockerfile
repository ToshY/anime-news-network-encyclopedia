ARG PYTHON_IMAGE_VERSION=3.11

FROM python:${PYTHON_IMAGE_VERSION}-slim-bookworm AS base

LABEL maintainer="ToshY (github.com/ToshY)"

ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY requirements.txt ./

RUN <<EOT bash
  apt-get update
  apt install -y git wget
  wget https://github.com/mikefarah/yq/releases/download/v4.44.5/yq_linux_amd64 -O /usr/bin/yq
  chmod +x /usr/bin/yq
  pip install --no-cache-dir -r requirements.txt
  pip install --no-cache-dir --upgrade --force-reinstall 'setuptools>=65.5.1'
EOT

FROM base AS dev

WORKDIR /app

COPY requirements.dev.txt ./

RUN pip install --no-cache-dir -r requirements.dev.txt
