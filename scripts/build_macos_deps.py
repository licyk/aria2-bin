#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEPS = {
    "zlib": {
        "version": "1.3.1",
        "url": "https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz",
        "directory": "zlib-1.3.1",
    },
    "expat": {
        "version": "2.5.0",
        "url": "https://github.com/libexpat/libexpat/releases/download/R_2_5_0/expat-2.5.0.tar.bz2",
        "directory": "expat-2.5.0",
    },
    "sqlite": {
        "version": "3430100",
        "url": "https://www.sqlite.org/2023/sqlite-autoconf-3430100.tar.gz",
        "directory": "sqlite-autoconf-3430100",
    },
}


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def safe_rmtree(path: Path) -> None:
    path = path.resolve()
    build_root = (ROOT / "build").resolve()
    if build_root not in path.parents and path != build_root:
        raise ValueError(f"refusing to remove path outside build/: {path}")
    if path.exists():
        shutil.rmtree(path)


def download(url: str, target: Path) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"+ download {url}", flush=True)
    urllib.request.urlretrieve(url, target)


def extract(archive: Path, destination: Path) -> None:
    safe_rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tf:
        tf.extractall(destination.parent)


def build_zlib(source: Path, prefix: Path, env: dict[str, str], jobs: int) -> None:
    run(["./configure", "--static", f"--prefix={prefix}"], source, env=env)
    run(["make", f"-j{jobs}", "install"], source, env=env)


def build_autoconf_dep(source: Path, prefix: Path, env: dict[str, str], jobs: int) -> None:
    run(["./configure", "--disable-shared", "--enable-static", f"--prefix={prefix}"], source, env=env)
    run(["make", f"-j{jobs}", "install"], source, env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build aria2 macOS static dependency prefix.")
    parser.add_argument("--arch", default=os.environ.get("ARCH", platform.machine()))
    parser.add_argument("--deployment-target", default=os.environ.get("MACOSX_DEPLOYMENT_TARGET", "11.0"))
    parser.add_argument("--prefix", type=Path, default=Path(os.environ.get("ARIA2_DEPS_PREFIX", ROOT / "build" / "macos-deps" / "prefix")))
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build" / "macos-deps")
    parser.add_argument("--jobs", type=int, default=int(os.environ.get("JOBS", os.cpu_count() or 2)))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if platform.system() != "Darwin":
        raise SystemExit("macOS dependency build must run on macOS")

    prefix = args.prefix.resolve()
    work_dir = args.work_dir.resolve()
    archives = work_dir / "archives"
    sources = work_dir / "sources"

    safe_rmtree(prefix)
    prefix.mkdir(parents=True, exist_ok=True)

    flags = f"-arch {args.arch} -mmacosx-version-min={args.deployment_target} -Os"
    env = os.environ.copy()
    env["CFLAGS"] = f"{flags} {env.get('CFLAGS', '')}".strip()
    env["CXXFLAGS"] = f"{flags} -std=c++11 {env.get('CXXFLAGS', '')}".strip()
    env["LDFLAGS"] = f"-arch {args.arch} -mmacosx-version-min={args.deployment_target} {env.get('LDFLAGS', '')}".strip()
    env["MACOSX_DEPLOYMENT_TARGET"] = args.deployment_target

    for name, meta in DEPS.items():
        archive = archives / Path(meta["url"]).name
        download(meta["url"], archive)
        source = sources / meta["directory"]
        extract(archive, source)
        if name == "zlib":
            build_zlib(source, prefix, env, args.jobs)
        else:
            build_autoconf_dep(source, prefix, env, args.jobs)

    print(prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
