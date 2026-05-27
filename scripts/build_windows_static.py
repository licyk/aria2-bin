#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Windows wheel from aria2-static-build artifacts.")
    parser.add_argument("--platform-tag", default=os.environ.get("ARIA2_WHEEL_PLATFORM_TAG", "win_amd64"))
    parser.add_argument("--release", default=os.environ.get("ARIA2_STATIC_RELEASE"))
    parser.add_argument("--static-build", default=os.environ.get("ARIA2_STATIC_BUILD"))
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    install_cmd = [
        sys.executable,
        "scripts/install_static_aria2.py",
        "--platform-tag",
        args.platform_tag,
    ]
    if args.release:
        install_cmd.extend(["--release", args.release])
    if args.static_build:
        install_cmd.extend(["--static-build", args.static_build])
    run(install_cmd)

    env = os.environ.copy()
    if platform.system() != "Windows":
        env["ARIA2_SKIP_STATIC_VERIFY"] = "1"

    run(
        [
            sys.executable,
            "scripts/build_wheel.py",
            "--skip-build",
            "--platform-tag",
            args.platform_tag,
            "--dist-dir",
            str(args.dist_dir),
        ],
        env=env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
