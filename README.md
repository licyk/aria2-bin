# aria2-bin

`aria2-bin` 用来构建包含预编译 `aria2c` 可执行文件的平台专用 Python wheel。
本仓库不会内置 aria2 源码；构建 wheel 时，构建后端会临时克隆 aria2 源码、
静态编译 `aria2c`，然后把生成的二进制文件打包进 wheel。

## 本地构建

请先安装系统构建依赖。Ubuntu 上直接构建本机 wheel 时，
默认的 `core` 静态构建配置需要：

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential git autoconf automake autopoint autotools-dev libtool gettext \
  pkg-config libssl-dev libexpat1-dev zlib1g-dev libsqlite3-dev python3 python3-venv
```

然后构建当前平台 wheel：

```bash
python3 scripts/build_wheel.py
```

正式分发 GNU/glibc Linux wheel 时，CI 使用 Ubuntu 容器构建静态 `aria2c`：

```bash
python3 scripts/build_linux_manylinux.py --arch x86_64
```

默认产物标签仍是 `manylinux_2_28_x86_64` 或 `manylinux_2_28_aarch64`。

分发 musl Linux wheel 时，CI 使用 Alpine/musl 容器源码构建。容器会先构建一份
静态 OpenSSL，并使用 `no-shared no-module enable-legacy`，避免 Alpine 系统
`openssl-libs-static` 在干净容器中运行时找不到 OpenSSL `legacy` provider：

```bash
python3 scripts/build_linux_musl.py --arch x86_64
```

如果需要临时参考 `aria2-wheel` 的做法，直接使用 `abcfy2/aria2-static-build`
的预编译静态产物，可以加 `--from-static`：

```bash
python3 scripts/build_linux_musl.py --arch x86_64 --from-static
```

GNU/glibc Linux 和 musllinux 源码构建路径都需要本机可用的 Docker。

默认构建参数如下：

```text
ARIA2_REF=release-1.37.0
ARIA2_STATIC_PROFILE=core
```

Windows，以及 musllinux 的 `--from-static` 备用路径，会使用 `ARIA2_REF` 推导
`aria2-static-build` 发布版本，例如 `release-1.37.0` 会下载 `1.37.0` 发布页
下的静态 zip。也可以显式覆盖：

```bash
ARIA2_STATIC_RELEASE=1.37.0 python3 scripts/build_linux_musl.py --arch x86_64 --from-static
```

GitHub Actions 手动运行 `build-wheels` 工作流时，可以在页面上填写 `aria2_ref`
来指定要构建的 aria2 release tag。Windows 使用预编译静态产物，因此不再适合
填写 branch 或 commit，除非同时改成源码构建路径或显式指定可用的
`ARIA2_STATIC_RELEASE`。

`core` 配置会启用 HTTPS、BitTorrent、Metalink、gzip、SQLite cookie、
XML-RPC 和 WebSocket 支持。为了让静态链接更容易在不同 Linux 环境中工作，
默认会关闭 NLS、SFTP 和异步 DNS。

如果想尝试更完整的功能集：

```bash
ARIA2_STATIC_PROFILE=full python3 scripts/build_wheel.py
```

`full` 配置会额外请求 SFTP 和异步 DNS，因此目标平台需要提供可静态链接的
`libssh2` 和 `c-ares` 依赖。

## macOS 构建

macOS 构建参考 aria2 上游做法：TLS 使用系统 AppleTLS，非系统依赖先构建为本地
静态库前缀，然后再编译 aria2。

```bash
brew install autoconf automake libtool pkg-config gettext
brew link --force gettext

export ARCH=arm64
export MACOSX_DEPLOYMENT_TARGET=11.0
export ARIA2_STATIC_PROFILE=macos-core
export ARIA2_WHEEL_PLATFORM_TAG=macosx_11_0_arm64
export ARIA2_DEPS_PREFIX="$PWD/build/macos-deps/prefix"
export CFLAGS="-arch $ARCH -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET -Os"
export CXXFLAGS="-arch $ARCH -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET -Os -std=c++11"
export LDFLAGS="-arch $ARCH -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET -Wl,-dead_strip"

python3 scripts/build_macos_deps.py
python3 scripts/build_wheel.py
```

Intel macOS 可以把 `ARCH` 改成 `x86_64`，并使用
`ARIA2_WHEEL_PLATFORM_TAG=macosx_10_13_x86_64`。

## Windows 构建

Windows CI 默认参考 `aria2-wheel` 的下载打包方案，在 `windows-2022` runner
上下载 `abcfy2/aria2-static-build` 发布页中的 `x86_64-w64-mingw32` 静态产物，
然后生成 `win_amd64` wheel。该静态产物使用 aria2 官方文档推荐的 mingw-w64
目标构建；官方源码交叉编译路线的核心形式是
`HOST=x86_64-w64-mingw32 ./mingw-config`。

```bash
python scripts/build_windows_static.py
```

默认目标是：

```text
ARIA2_WHEEL_PLATFORM_TAG=win_amd64
```

仓库中仍保留 `scripts/build_windows_msys2.py`、`scripts/build_windows_mingw.py`
和 `docker/windows-mingw.Dockerfile`，用于排查或复刻源码构建路线，但 CI 不再
默认使用它们。

## 使用 uv 构建

本项目提供了自定义 PEP 517 build backend，因此也可以用 `uv` 调用：

```bash
uv build --wheel
```

如果没有安装 `uv`，直接执行 `python3 scripts/build_wheel.py` 也可以完成构建。

## 安装和验证

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install dist/aria2_bin-*.whl
aria2c --version
```

## 平台 wheel

每个目标平台应该单独构建一个 wheel，不建议把所有平台的二进制文件放进同一个
wheel。当前 CI 会构建这些目标：

```text
manylinux_2_28_x86_64
manylinux_2_28_aarch64
musllinux_1_2_x86_64
musllinux_1_2_aarch64
macosx_10_13_x86_64
macosx_11_0_arm64
win_amd64
```

交叉构建或手动指定平台标签时，可以覆盖 `ARIA2_WHEEL_PLATFORM_TAG`：

```bash
ARIA2_WHEEL_PLATFORM_TAG=manylinux_2_28_x86_64 python3 scripts/build_wheel.py
ARIA2_WHEEL_PLATFORM_TAG=musllinux_1_2_x86_64 python3 scripts/build_wheel.py
ARIA2_WHEEL_PLATFORM_TAG=macosx_11_0_arm64 python3 scripts/build_wheel.py
ARIA2_WHEEL_PLATFORM_TAG=win_amd64 python3 scripts/build_wheel.py
```

wheel 标签使用 `py3-none-<platform>`，因为包里没有 CPython 扩展模块，
只包含外部可执行文件。

## 许可证说明

打包进去的可执行文件来自 aria2，aria2 使用 GPL-2.0-or-later 许可证分发。
构建脚本会在克隆到的 aria2 源码中查找 `COPYING` 和 `LICENSE.OpenSSL`，
如果存在，就把它们一起复制进 wheel。
