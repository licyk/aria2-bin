#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "https://github.com/aria2/aria2.git"
DEFAULT_REF = "release-1.37.0"


PROFILES = {
    "core": [
        "--with-openssl",
        "--without-gnutls",
        "--disable-nls",
        "--without-libnettle",
        "--without-libgcrypt",
        "--without-libxml2",
        "--with-libexpat",
        "--with-libz",
        "--with-sqlite3",
        "--without-libcares",
        "--without-libssh2",
    ],
    "full": [
        "--with-openssl",
        "--without-gnutls",
        "--disable-nls",
        "--without-libnettle",
        "--without-libgcrypt",
        "--without-libxml2",
        "--with-libexpat",
        "--with-libz",
        "--with-sqlite3",
        "--with-libcares",
        "--with-libssh2",
    ],
    "macos-core": [
        "--without-openssl",
        "--without-gnutls",
        "--with-appletls",
        "--disable-nls",
        "--without-libnettle",
        "--without-libgmp",
        "--without-libgcrypt",
        "--without-libxml2",
        "--with-libexpat",
        "--with-libz",
        "--with-sqlite3",
        "--without-libcares",
        "--without-libssh2",
    ],
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


def clone_source(repo: str, ref: str, source_dir: Path) -> None:
    safe_rmtree(source_dir)
    source_dir.parent.mkdir(parents=True, exist_ok=True)

    try:
        run(["git", "clone", "--depth", "1", "--branch", ref, repo, str(source_dir)], ROOT)
    except subprocess.CalledProcessError:
        safe_rmtree(source_dir)
        run(["git", "clone", "--depth", "1", repo, str(source_dir)], ROOT)
        run(["git", "fetch", "--depth", "1", "origin", ref], source_dir)
        run(["git", "checkout", "FETCH_HEAD"], source_dir)


def detect_binary(source_dir: Path) -> Path:
    candidates = [
        source_dir / "src" / "aria2c",
        source_dir / "src" / "aria2c.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("could not find built aria2c under aria2/src")


def copy_license_files(source_dir: Path, license_dir: Path) -> None:
    license_dir.mkdir(parents=True, exist_ok=True)
    for name in ("COPYING", "LICENSE.OpenSSL"):
        source = source_dir / name
        if source.exists():
            shutil.copy2(source, license_dir / f"aria2-{name}")


def append_env_flag(env: dict[str, str], key: str, value: str) -> None:
    current = env.get(key)
    env[key] = f"{value} {current}" if current else value


def prepend_env_path(env: dict[str, str], key: str, value: Path) -> None:
    current = env.get(key)
    env[key] = f"{value}{os.pathsep}{current}" if current else str(value)


def configure_dependency_prefix(env: dict[str, str], prefix: Path | None) -> None:
    if not prefix:
        return

    prefix = prefix.resolve()
    append_env_flag(env, "CPPFLAGS", f"-I{prefix / 'include'}")
    append_env_flag(env, "LDFLAGS", f"-L{prefix / 'lib'}")
    prepend_env_path(env, "PKG_CONFIG_PATH", prefix / "lib" / "pkgconfig")


def ensure_configure(source_dir: Path, env: dict[str, str]) -> None:
    configure = source_dir / "configure"
    if configure.exists():
        configure.chmod(configure.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return
    run(["autoreconf", "-i"], source_dir, env=env)


def build(args: argparse.Namespace) -> Path:
    source_dir = args.work_dir / "src"
    clone_source(args.repo, args.ref, source_dir)

    env = os.environ.copy()
    if args.pkg_config:
        env["PKG_CONFIG"] = args.pkg_config
    configure_dependency_prefix(env, args.deps_prefix)

    configure_args = ["./configure", "ARIA2_STATIC=yes", *PROFILES[args.profile]]
    if args.configure_arg:
        configure_args.extend(args.configure_arg)

    ensure_configure(source_dir, env)
    run(configure_args, source_dir, env=env)
    run(["make", f"-j{args.jobs}"], source_dir, env=env)

    built_binary = detect_binary(source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built_binary, args.output)
    args.output.chmod(0o755)

    strip = env.get("STRIP") or shutil.which("strip")
    if not args.no_strip and strip:
        run([strip, str(args.output)], ROOT)

    copy_license_files(source_dir, ROOT / "src" / "aria2_bin" / "licenses")

    if not args.no_verify:
        run([sys.executable, str(ROOT / "scripts" / "verify_static.py"), str(args.output)], ROOT)

    return args.output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clone and statically build aria2c.")
    parser.add_argument("--repo", default=os.environ.get("ARIA2_REPO", DEFAULT_REPO))
    parser.add_argument("--ref", default=os.environ.get("ARIA2_REF", DEFAULT_REF))
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default=os.environ.get("ARIA2_STATIC_PROFILE", "core"),
        help="'core' is easiest to static-link; 'full' also enables SFTP and async DNS; 'macos-core' uses AppleTLS.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.environ.get("ARIA2_BUILD_WORKDIR", ROOT / "build" / "aria2")),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.environ.get("ARIA2_BINARY", ROOT / "src" / "aria2_bin" / "bin" / "aria2c")),
    )
    parser.add_argument("--jobs", type=int, default=int(os.environ.get("JOBS", os.cpu_count() or 2)))
    parser.add_argument(
        "--deps-prefix",
        type=Path,
        default=Path(os.environ["ARIA2_DEPS_PREFIX"]) if os.environ.get("ARIA2_DEPS_PREFIX") else None,
        help="Prefix containing static dependency headers, libraries, and pkg-config files.",
    )
    parser.add_argument(
        "--pkg-config",
        default=os.environ.get("PKG_CONFIG", "pkg-config"),
        help="pkg-config executable. aria2 adds --static when ARIA2_STATIC=yes.",
    )
    parser.add_argument(
        "--configure-arg",
        action="append",
        help="Extra argument appended to aria2 ./configure. Can be passed more than once.",
    )
    parser.add_argument("--no-verify", action="store_true", default=os.environ.get("ARIA2_NO_VERIFY") == "1")
    parser.add_argument("--no-strip", action="store_true", default=os.environ.get("ARIA2_NO_STRIP") == "1")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    binary = build(args)
    print(f"built {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
