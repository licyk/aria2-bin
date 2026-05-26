ARG MANYLINUX_IMAGE=quay.io/pypa/manylinux_2_28_x86_64
FROM ${MANYLINUX_IMAGE}

RUN set -eux; \
    dnf install -y dnf-plugins-core; \
    (dnf config-manager --set-enabled powertools || \
        dnf config-manager --set-enabled PowerTools || \
        dnf config-manager --set-enabled crb || \
        true); \
    dnf install -y \
    autoconf \
    automake \
    expat-devel \
    expat-static \
    file \
    gettext-devel \
    git \
    glibc-static \
    libtool \
    libstdc++-static \
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
