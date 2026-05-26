#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def copy_from_container(container: str, source: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["docker", "cp", f"{container}:{source}", str(target)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Windows aria2c.exe with mingw-w64 Docker.")
    parser.add_argument("--host", default=os.environ.get("MINGW_HOST", "x86_64-w64-mingw32"))
    parser.add_argument("--platform-tag", default=os.environ.get("ARIA2_WHEEL_PLATFORM_TAG", "win_amd64"))
    parser.add_argument("--image", default=os.environ.get("ARIA2_MINGW_IMAGE", "aria2-bin-mingw"))
    parser.add_argument("--ref", default=os.environ.get("ARIA2_REF", "release-1.37.0"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = ROOT / "src" / "aria2_bin" / "bin" / "aria2c.exe"
    license_dir = ROOT / "src" / "aria2_bin" / "licenses"

    run(
        [
            "docker",
            "build",
            "-f",
            "docker/windows-mingw.Dockerfile",
            "-t",
            args.image,
            "--build-arg",
            f"HOST={args.host}",
            "--build-arg",
            f"ARIA2_REF={args.ref}",
            ".",
        ]
    )

    container = subprocess.check_output(["docker", "create", args.image], text=True).strip()
    try:
        copy_from_container(container, "/aria2/src/aria2c.exe", output)
        output.chmod(0o755)
        for name in ("COPYING", "LICENSE.OpenSSL"):
            copy_from_container(container, f"/aria2/{name}", license_dir / f"aria2-{name}")
    finally:
        run(["docker", "rm", "-f", container])

    if not output.exists():
        raise SystemExit(f"missing Windows binary: {output}")

    if shutil.which("file"):
        run(["file", str(output)])

    env = os.environ.copy()
    env["ARIA2_SKIP_STATIC_VERIFY"] = "1"
    run(["python3", "scripts/build_wheel.py", "--skip-build", "--platform-tag", args.platform_tag], env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
