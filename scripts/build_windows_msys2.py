#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "https://github.com/aria2/aria2.git"
DEFAULT_REF = "release-1.37.0"
DEFAULT_MSYSTEM = "UCRT64"

MSYSTEM_CONFIGS = {
    "MINGW64": {
        "host": "x86_64-w64-mingw32",
        "prefix": "/mingw64",
    },
    "UCRT64": {
        "host": "x86_64-w64-mingw32",
        "prefix": "/ucrt64",
    },
}

CONFIGURE_ARGS = [
    "--without-included-gettext",
    "--disable-nls",
    "--without-openssl",
    "--without-gnutls",
    "--with-wintls",
    "--without-libnettle",
    "--without-libgmp",
    "--without-libgcrypt",
    "--without-libxml2",
    "--with-libexpat",
    "--with-libz",
    "--with-sqlite3",
    "--without-libcares",
    "--without-libssh2",
    "ARIA2_STATIC=yes",
]

DISALLOWED_DLL_FRAGMENTS = (
    "libgcc",
    "libstdc++",
    "libwinpthread",
    "libssp",
    "libz",
    "zlib",
    "libexpat",
    "sqlite",
    "libiconv",
    "libintl",
    "libcrypto",
    "libssl",
    "libgnutls",
)


def msystem_config(msystem: str) -> dict[str, str]:
    normalized = msystem.upper()
    try:
        return MSYSTEM_CONFIGS[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(MSYSTEM_CONFIGS))
        raise SystemExit(f"unsupported MSYSTEM={msystem}; supported values: {supported}") from exc


def run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def run_output(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    print(f"+ {' '.join(cmd)}", flush=True)
    return subprocess.check_output(cmd, cwd=cwd, env=env, text=True)


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
        run(["git", "clone", "--depth", "1", "--branch", ref, repo, str(source_dir)])
    except subprocess.CalledProcessError:
        safe_rmtree(source_dir)
        run(["git", "clone", "--depth", "1", repo, str(source_dir)])
        run(["git", "fetch", "--depth", "1", "origin", ref], source_dir)
        run(["git", "checkout", "FETCH_HEAD"], source_dir)


def find_bash() -> Path:
    if os.environ.get("MSYS2_BASH"):
        return Path(os.environ["MSYS2_BASH"])
    candidates = [
        Path(os.environ.get("MSYS2_LOCATION", "")) / "usr" / "bin" / "bash.exe",
        Path("C:/msys64/usr/bin/bash.exe"),
    ]
    for candidate in candidates:
        if str(candidate) and candidate.exists():
            return candidate
    found = shutil.which("bash")
    if found:
        return Path(found)
    raise SystemExit("could not find MSYS2 bash; run this after msys2/setup-msys2")


def msys_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt" and resolved.drive:
        posix = resolved.as_posix()
        return f"/{resolved.drive[0].lower()}{posix[2:]}"
    return resolved.as_posix()


def bash_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env["MSYSTEM"] = args.msystem.upper()
    env["CHERE_INVOKING"] = "1"
    env["MSYS2_PATH_TYPE"] = "minimal"
    return env


def run_bash(script: str, cwd: Path, args: argparse.Namespace) -> None:
    prefix = msystem_config(args.msystem)["prefix"]
    command = "\n".join(
        [
            "set -euo pipefail",
            f"export PATH={prefix}/bin:/usr/bin:$PATH",
            f"cd {shlex.quote(msys_path(cwd))}",
            script,
        ]
    )
    run([str(find_bash()), "-lc", command], env=bash_env(args))


def run_bash_output(script: str, cwd: Path, args: argparse.Namespace) -> str:
    prefix = msystem_config(args.msystem)["prefix"]
    command = "\n".join(
        [
            "set -euo pipefail",
            f"export PATH={prefix}/bin:/usr/bin:$PATH",
            f"cd {shlex.quote(msys_path(cwd))}",
            script,
        ]
    )
    return run_output([str(find_bash()), "-lc", command], env=bash_env(args))


def build_aria2(source_dir: Path, jobs: int, args: argparse.Namespace) -> Path:
    config = msystem_config(args.msystem)
    host = config["host"]
    prefix = config["prefix"]
    configure_args = " ".join(
        shlex.quote(arg) for arg in [f"--host={host}", f"--prefix={prefix}", *CONFIGURE_ARGS]
    )
    run_bash(
        f"""
if [ ! -f ./configure ]; then
  autoreconf -i
fi
chmod +x ./configure
PKG_CONFIG="$(command -v pkg-config || command -v pkgconf)"
./configure {configure_args} \\
  CPPFLAGS="-I{prefix}/include" \\
  LDFLAGS="-L{prefix}/lib -static -static-libgcc -static-libstdc++" \\
  PKG_CONFIG="$PKG_CONFIG" \\
  PKG_CONFIG_PATH="{prefix}/lib/pkgconfig"
make -j{jobs}
{host}-strip src/aria2c.exe
""",
        source_dir,
        args,
    )

    built = source_dir / "src" / "aria2c.exe"
    if not built.exists():
        raise SystemExit(f"missing built Windows binary: {built}")
    return built


def verify_imports(binary: Path, args: argparse.Namespace) -> None:
    host = msystem_config(args.msystem)["host"]
    output = run_bash_output(
        f"{host}-objdump -p {shlex.quote(msys_path(binary))} | sed -n 's/^[[:space:]]*DLL Name: //p'",
        ROOT,
        args,
    )
    dlls = [line.strip() for line in output.splitlines() if line.strip()]
    print("Imported DLLs:")
    for dll in dlls:
        print(f"  {dll}")

    bad = [
        dll
        for dll in dlls
        if any(fragment in dll.lower() for fragment in DISALLOWED_DLL_FRAGMENTS)
    ]
    if bad:
        raise SystemExit(f"Windows binary depends on non-system DLLs: {', '.join(bad)}")


def copy_license_files(source_dir: Path, license_dir: Path) -> None:
    license_dir.mkdir(parents=True, exist_ok=True)
    for name in ("COPYING", "LICENSE.OpenSSL"):
        source = source_dir / name
        if source.exists():
            shutil.copy2(source, license_dir / f"aria2-{name}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Windows aria2c.exe with native MSYS2 MinGW.")
    parser.add_argument("--repo", default=os.environ.get("ARIA2_REPO", DEFAULT_REPO))
    parser.add_argument("--ref", default=os.environ.get("ARIA2_REF", DEFAULT_REF))
    parser.add_argument("--platform-tag", default=os.environ.get("ARIA2_WHEEL_PLATFORM_TAG", "win_amd64"))
    parser.add_argument("--msystem", choices=sorted(MSYSTEM_CONFIGS), default=os.environ.get("MSYSTEM", DEFAULT_MSYSTEM).upper())
    parser.add_argument("--jobs", type=int, default=int(os.environ.get("JOBS", os.cpu_count() or 2)))
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build" / "aria2-windows-msys2")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_dir = args.work_dir / "src"
    output = ROOT / "src" / "aria2_bin" / "bin" / "aria2c.exe"

    clone_source(args.repo, args.ref, source_dir)
    built = build_aria2(source_dir, args.jobs, args)

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, output)
    output.chmod(0o755)
    copy_license_files(source_dir, ROOT / "src" / "aria2_bin" / "licenses")
    verify_imports(output, args)

    run([sys.executable, "scripts/build_wheel.py", "--skip-build", "--platform-tag", args.platform_tag])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
