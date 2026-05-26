FROM alpine:3.20

RUN apk add --no-cache \
    autoconf \
    automake \
    build-base \
    expat-dev \
    expat-static \
    file \
    gettext \
    gettext-dev \
    git \
    libtool \
    openssl-dev \
    openssl-libs-static \
    pkgconf \
    python3 \
    sqlite-dev \
    sqlite-static \
    zlib-dev \
    zlib-static

WORKDIR /workspace
