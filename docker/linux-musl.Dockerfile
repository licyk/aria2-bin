FROM alpine:3.20

ARG OPENSSL_VERSION=3.5.6

ENV ARIA2_DEPS_PREFIX=/opt/aria2-deps

RUN apk add --no-cache \
    autoconf \
    automake \
    build-base \
    ca-certificates \
    curl \
    expat-dev \
    expat-static \
    file \
    gettext \
    gettext-dev \
    git \
    linux-headers \
    libtool \
    perl \
    pkgconf \
    py3-pip \
    python3 \
    sqlite-dev \
    sqlite-static \
    zlib-dev \
    zlib-static

WORKDIR /tmp/openssl

RUN curl -fsSL -o openssl.tar.gz "https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz" && \
    tar -xzf openssl.tar.gz --strip-components=1 && \
    ./config \
      no-shared \
      no-module \
      enable-legacy \
      no-tests \
      --prefix="$ARIA2_DEPS_PREFIX" \
      --openssldir="$ARIA2_DEPS_PREFIX/ssl" && \
    make -j"$(nproc)" install_sw && \
    rm -rf /tmp/openssl

WORKDIR /workspace
