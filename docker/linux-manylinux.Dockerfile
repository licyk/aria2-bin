ARG MANYLINUX_IMAGE=quay.io/pypa/manylinux_2_28_x86_64
FROM ${MANYLINUX_IMAGE}

RUN dnf install -y \
    autoconf \
    automake \
    expat-devel \
    expat-static \
    file \
    gettext-devel \
    git \
    libtool \
    make \
    openssl-devel \
    openssl-static \
    pkgconf-pkg-config \
    sqlite-devel \
    sqlite-static \
    zlib-devel \
    zlib-static && \
    dnf clean all

WORKDIR /workspace
