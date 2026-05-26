# aria2-bin

`aria2-bin` 用来构建包含预编译 `aria2c` 可执行文件的平台专用 Python wheel。
本仓库不会内置 aria2 源码；构建 wheel 时，构建后端会临时克隆 aria2 源码、
静态编译 `aria2c`，然后把生成的二进制文件打包进 wheel。

## 本地构建

请先安装系统构建依赖。Ubuntu 上直接构建本机 `linux_x86_64` wheel 时，
默认的 `core` 静态构建配置需要：

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential git autoconf automake autopoint autotools-dev libtool gettext \
  pkg-config libssl-dev libexpat1-dev zlib1g-dev libsqlite3-dev python3 python3-venv
```

然后构建 wheel：

```bash
python3 scripts/build_wheel.py
```

正式分发 Linux wheel 时，推荐用 musl 容器构建 `musllinux` wheel：

```bash
python3 scripts/build_linux_musl.py --arch x86_64
```

这条路径需要本机可用的 Docker。

默认构建参数如下：

```text
ARIA2_REF=release-1.37.0
ARIA2_STATIC_PROFILE=core
```

GitHub Actions 手动运行 `build-wheels` 工作流时，可以在页面上填写 `aria2_ref`
来指定要构建的 aria2 tag、分支或 commit。

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

Windows CI 默认在 `windows-2022` runner 上使用 MSYS2 UCRT64/MinGW 直接编译，
依赖通过 MSYS2 `pacman` 安装，避免在 Docker 构建阶段逐个下载第三方源码。
构建脚本会使用 WinTLS，静态链接 zlib、expat 和 sqlite，然后生成 `win_amd64`
wheel。

```bash
python scripts/build_windows_msys2.py
```

默认目标是：

```text
MSYSTEM=UCRT64
ARIA2_WHEEL_PLATFORM_TAG=win_amd64
```

如果需要回退到传统 MINGW64 环境，可以设置 `MSYSTEM=MINGW64`，但 CI 默认使用
UCRT64。

仓库中仍保留 `scripts/build_windows_mingw.py` 和 `docker/windows-mingw.Dockerfile`，
用于复刻 aria2 上游的 Linux mingw-w64 交叉编译路线，但 CI 不再默认使用它。

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
musllinux_1_2_x86_64
musllinux_1_2_aarch64
macosx_10_13_x86_64
macosx_11_0_arm64
win_amd64
```

交叉构建或手动指定平台标签时，可以覆盖 `ARIA2_WHEEL_PLATFORM_TAG`：

```bash
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
