#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def default_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    if machine in {"aarch64", "arm64"}:
        return "aarch64"
    raise SystemExit(f"unsupported Linux musl architecture: {machine}")


def run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a musllinux wheel in an Alpine container.")
    parser.add_argument("--arch", default=os.environ.get("ARIA2_MUSL_ARCH", default_arch()))
    parser.add_argument("--image", default=os.environ.get("ARIA2_MUSL_IMAGE", "aria2-bin-linux-musl"))
    parser.add_argument("--platform-tag", default=os.environ.get("ARIA2_WHEEL_PLATFORM_TAG"))
    parser.add_argument("--profile", default=os.environ.get("ARIA2_STATIC_PROFILE", "core"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    platform_tag = args.platform_tag or f"musllinux_1_2_{args.arch}"

    run(["docker", "build", "-f", "docker/linux-musl.Dockerfile", "-t", args.image, "."])

    env_args = []
    for name, value in {
        "ARIA2_REF": os.environ.get("ARIA2_REF", "release-1.37.0"),
        "ARIA2_REPO": os.environ.get("ARIA2_REPO", "https://github.com/aria2/aria2.git"),
        "ARIA2_STATIC_PROFILE": args.profile,
        "ARIA2_WHEEL_PLATFORM_TAG": platform_tag,
        "ARIA2_SKIP_RUN_VERIFY": "1",
    }.items():
        env_args.extend(["-e", f"{name}={value}"])

    run(
        [
            "docker",
            "run",
            "--rm",
            *env_args,
            "-v",
            f"{ROOT}:/workspace",
            "-w",
            "/workspace",
            args.image,
            "python3",
            "scripts/build_wheel.py",
            "--platform-tag",
            platform_tag,
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
