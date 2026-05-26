ARG LINUX_IMAGE=ubuntu:24.04
FROM ${LINUX_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    autopoint \
    binutils \
    ca-certificates \
    file \
    g++ \
    gettext \
    git \
    libexpat1-dev \
    libssl-dev \
    libsqlite3-dev \
    libtool \
    make \
    pkg-config \
    python3 \
    python3-pip \
    python3-venv \
    zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
