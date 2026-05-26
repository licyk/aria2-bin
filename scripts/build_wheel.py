#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from email.message import Message
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only used on Python < 3.11
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "aria2_bin"
PROJECT_FILE = ROOT / "pyproject.toml"


def normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def read_project() -> dict:
    with PROJECT_FILE.open("rb") as f:
        return tomllib.load(f)["project"]


def local_platform_tag() -> str:
    override = os.environ.get("ARIA2_WHEEL_PLATFORM_TAG")
    if override:
        return override
    return sysconfig.get_platform().replace("-", "_").replace(".", "_")


def binary_name(platform_tag: str) -> str:
    return "aria2c.exe" if platform_tag.startswith("win") else "aria2c"


def sha256_record(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}", str(len(data))


def zip_write(zf: zipfile.ZipFile, source: Path, arcname: str, executable: bool = False) -> None:
    info = zipfile.ZipInfo(arcname)
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    with source.open("rb") as f:
        zf.writestr(info, f.read())


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def metadata_text(project: dict) -> str:
    msg = Message()
    msg["Metadata-Version"] = "2.3"
    msg["Name"] = project["name"]
    msg["Version"] = project["version"]
    msg["Summary"] = project["description"]
    msg["Requires-Python"] = project.get("requires-python", ">=3.8")
    msg["License"] = project.get("license", {}).get("text", "GPL-2.0-or-later")
    msg["Description-Content-Type"] = "text/markdown"
    for classifier in project.get("classifiers", []):
        msg["Classifier"] = classifier

    body = ""
    readme = ROOT / "README.md"
    if readme.exists():
        body = readme.read_text(encoding="utf-8")
    return msg.as_string() + "\n" + body


def wheel_text(platform_tag: str) -> str:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: aria2-bin custom wheel builder\n"
        "Root-Is-Purelib: false\n"
        f"Tag: py3-none-{platform_tag}\n"
    )


def prepare_metadata(metadata_directory: Path) -> str:
    project = read_project()
    dist = normalize_dist_name(project["name"])
    dist_info = f"{dist}-{project['version']}.dist-info"
    out = metadata_directory / dist_info
    out.mkdir(parents=True, exist_ok=True)
    write_text_file(out / "METADATA", metadata_text(project))
    write_text_file(out / "WHEEL", wheel_text(local_platform_tag()))
    return dist_info


def ensure_binary(platform_tag: str, skip_build: bool) -> Path:
    bin_path = PACKAGE_DIR / "bin" / binary_name(platform_tag)
    if skip_build:
        if not bin_path.exists():
            raise SystemExit(f"ARIA2_SKIP_BUILD=1 but binary is missing: {bin_path}")
        return bin_path

    env = os.environ.copy()
    env["ARIA2_BINARY"] = str(bin_path)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_aria2.py")], cwd=ROOT, env=env, check=True)
    return bin_path


def collect_package_files(platform_tag: str) -> list[tuple[Path, str, bool]]:
    files: list[tuple[Path, str, bool]] = []
    target_binary = binary_name(platform_tag)
    for path in sorted(PACKAGE_DIR.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.parent == PACKAGE_DIR / "bin" and path.name != target_binary:
            continue
        rel = path.relative_to(ROOT / "src").as_posix()
        executable = path.parent.name == "bin" and path.name.startswith("aria2c")
        files.append((path, rel, executable))
    return files


def build_wheel_from_config(wheel_directory: Path, config_settings: dict | None = None) -> str:
    project = read_project()
    dist = normalize_dist_name(project["name"])
    version = project["version"]
    platform_tag = local_platform_tag()
    skip_build = os.environ.get("ARIA2_SKIP_BUILD") == "1"

    binary = ensure_binary(platform_tag, skip_build)
    if os.environ.get("ARIA2_SKIP_STATIC_VERIFY") != "1":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_static.py"), str(binary)], cwd=ROOT, check=True)

    wheel_directory.mkdir(parents=True, exist_ok=True)
    wheel_name = f"{dist}-{version}-py3-none-{platform_tag}.whl"
    wheel_path = wheel_directory / wheel_name
    dist_info = f"{dist}-{version}.dist-info"

    temp_meta = ROOT / "build" / "wheel-meta" / dist_info
    if temp_meta.exists():
        shutil.rmtree(temp_meta)
    temp_meta.mkdir(parents=True, exist_ok=True)

    write_text_file(temp_meta / "METADATA", metadata_text(project))
    write_text_file(temp_meta / "WHEEL", wheel_text(platform_tag))
    write_text_file(temp_meta / "entry_points.txt", "[console_scripts]\naria2c = aria2_bin._run:main\n")
    write_text_file(temp_meta / "top_level.txt", "aria2_bin\n")

    records: list[list[str]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source, arcname, executable in collect_package_files(platform_tag):
            zip_write(zf, source, arcname, executable)
            records.append([arcname, *sha256_record(source)])

        for meta_file in sorted(temp_meta.iterdir()):
            arcname = f"{dist_info}/{meta_file.name}"
            zip_write(zf, meta_file, arcname)
            records.append([arcname, *sha256_record(meta_file)])

        record_name = f"{dist_info}/RECORD"
        record_lines: list[str] = []
        for row in records:
            record_lines.append(",".join(csv_escape(part) for part in row))
        record_lines.append(f"{record_name},,")
        zf.writestr(record_name, "\n".join(record_lines) + "\n")

    print(f"built wheel: {wheel_path}")
    return wheel_name


def csv_escape(value: str) -> str:
    output = []
    class Writer:
        def write(self, text: str) -> None:
            output.append(text)

    csv.writer(Writer(), lineterminator="").writerow([value])
    return "".join(output)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a platform wheel containing aria2c.")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--skip-build", action="store_true", help="Use an existing src/aria2_bin/bin/aria2c.")
    parser.add_argument("--platform-tag", help="Override wheel platform tag, e.g. musllinux_1_2_x86_64.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.skip_build:
        os.environ["ARIA2_SKIP_BUILD"] = "1"
    if args.platform_tag:
        os.environ["ARIA2_WHEEL_PLATFORM_TAG"] = args.platform_tag
    build_wheel_from_config(args.dist_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
