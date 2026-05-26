#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


def run_output(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout


def command_exists(name: str) -> bool:
    return subprocess.run(
        ["sh", "-c", f"command -v {name} >/dev/null 2>&1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def verify_linux(binary: Path) -> None:
    _, file_output = run_output(["file", str(binary)])
    print(file_output.rstrip())

    if command_exists("readelf"):
        _, headers = run_output(["readelf", "-l", str(binary)])
        _, dynamic = run_output(["readelf", "-d", str(binary)])
        if "INTERP" in headers:
            raise SystemExit("binary has a dynamic interpreter; expected a static aria2c")
        if "(NEEDED)" in dynamic:
            raise SystemExit("binary has dynamic NEEDED entries; expected a static aria2c")
        return

    code, ldd_output = run_output(["ldd", str(binary)])
    print(ldd_output.rstrip())

    static_markers = (
        "not a dynamic executable",
        "statically linked",
        "static-pie linked",
    )
    combined = f"{file_output}\n{ldd_output}".lower()
    if not any(marker in combined for marker in static_markers):
        raise SystemExit("binary is dynamically linked; expected a static aria2c")
    if code not in (0, 1):
        raise SystemExit(f"ldd failed with exit code {code}")


def verify_macos(binary: Path, strict: bool) -> None:
    code, output = run_output(["otool", "-L", str(binary)])
    print(output.rstrip())
    if strict and code == 0 and "\n" in output.strip():
        raise SystemExit("macOS fully static binaries are uncommon; otool reported dylib dependencies")


def verify_version(binary: Path) -> None:
    try:
        code, output = run_output([str(binary), "--version"])
    except OSError as exc:
        raise SystemExit(f"aria2c --version could not run: {exc}") from exc
    print(output.splitlines()[0] if output else "")
    if code != 0 or "aria2 version" not in output:
        raise SystemExit("aria2c --version failed")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify an aria2c binary before packaging.")
    parser.add_argument("binary", type=Path)
    parser.add_argument("--strict-macos", action="store_true")
    parser.add_argument("--skip-run", action="store_true", default=os.environ.get("ARIA2_SKIP_RUN_VERIFY") == "1")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    binary = args.binary.resolve()
    if not binary.exists():
        raise SystemExit(f"missing binary: {binary}")

    system = platform.system()
    if system == "Linux":
        verify_linux(binary)
    elif system == "Darwin":
        verify_macos(binary, args.strict_macos)
    elif system == "Windows":
        print("Windows static dependency verification is not implemented; running --version only.")
    else:
        print(f"Static dependency verification is not implemented for {system}; running --version only.")

    if args.skip_run:
        print("skipping aria2c --version runtime check")
    elif os.access(binary, os.X_OK) or system == "Windows":
        verify_version(binary)
    else:
        raise SystemExit(f"binary is not executable: {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
