#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "aria2_bin"
DEFAULT_REF = "release-1.37.0"
DEFAULT_URL_TEMPLATE = (
    "https://github.com/abcfy2/aria2-static-build/releases/download/"
    "{release}/aria2-{build}_static.zip"
)
LICENSES = ("COPYING", "LICENSE.OpenSSL")
VERSION_RE = re.compile(r"^(?:release-|v)?(?P<version>\d+\.\d+\.\d+(?:[A-Za-z0-9._+-]*)?)$")


STATIC_BUILD_BY_PLATFORM = {
    "musllinux_1_1_x86_64": "x86_64-linux-musl",
    "musllinux_1_2_x86_64": "x86_64-linux-musl",
    "musllinux_1_1_aarch64": "aarch64-linux-musl",
    "musllinux_1_2_aarch64": "aarch64-linux-musl",
    "win32": "i686-w64-mingw32",
    "win_amd64": "x86_64-w64-mingw32",
}


def binary_name(platform_tag: str) -> str:
    return "aria2c.exe" if platform_tag.startswith("win") else "aria2c"


def static_release_from_ref(ref: str) -> str:
    match = VERSION_RE.match(ref)
    if not match:
        raise SystemExit(
            f"cannot derive aria2-static-build release from ARIA2_REF={ref!r}; "
            "set ARIA2_STATIC_RELEASE to a release such as 1.37.0"
        )
    return match.group("version")


def default_static_release() -> str:
    if os.environ.get("ARIA2_STATIC_RELEASE"):
        return os.environ["ARIA2_STATIC_RELEASE"]
    return static_release_from_ref(os.environ.get("ARIA2_REF", DEFAULT_REF))


def static_build_for_platform(platform_tag: str, override: str | None = None) -> str:
    if override:
        return override
    try:
        return STATIC_BUILD_BY_PLATFORM[platform_tag]
    except KeyError as exc:
        supported = ", ".join(sorted(STATIC_BUILD_BY_PLATFORM))
        raise SystemExit(f"unsupported static aria2 platform tag {platform_tag!r}; supported: {supported}") from exc


def download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "aria2-bin-builder"})
    print(f"download {url}")
    with urllib.request.urlopen(request, timeout=120) as response:
        with target.open("wb") as f:
            shutil.copyfileobj(response, f)


def find_binary_member(zip_file: zipfile.ZipFile, name: str) -> zipfile.ZipInfo:
    matches = [
        member
        for member in zip_file.infolist()
        if not member.is_dir() and PurePosixPath(member.filename).name == name
    ]
    if not matches:
        names = ", ".join(member.filename for member in zip_file.infolist())
        raise SystemExit(f"could not find {name!r} in downloaded archive; members: {names}")
    return sorted(matches, key=lambda member: len(PurePosixPath(member.filename).parts))[0]


def extract_binary(archive: Path, output: Path, name: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zip_file:
        member = find_binary_member(zip_file, name)
        with zip_file.open(member) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target)

        mode = (member.external_attr >> 16) & 0o7777
        output.chmod(mode or 0o755)

    print(f"installed {output}")


def license_ref_for_release(release: str) -> str:
    if os.environ.get("ARIA2_LICENSE_REF"):
        return os.environ["ARIA2_LICENSE_REF"]
    ref = os.environ.get("ARIA2_REF")
    if ref and ref.startswith("release-"):
        return ref
    return f"release-{release}"


def download_licenses(ref: str, license_dir: Path) -> None:
    license_dir.mkdir(parents=True, exist_ok=True)
    for name in LICENSES:
        url = f"https://raw.githubusercontent.com/aria2/aria2/{ref}/{name}"
        download_file(url, license_dir / f"aria2-{name}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install a prebuilt static aria2c binary into the wheel package.")
    parser.add_argument("--platform-tag", default=os.environ.get("ARIA2_WHEEL_PLATFORM_TAG"))
    parser.add_argument("--release", default=os.environ.get("ARIA2_STATIC_RELEASE"))
    parser.add_argument("--static-build", default=os.environ.get("ARIA2_STATIC_BUILD"))
    parser.add_argument("--url-template", default=os.environ.get("ARIA2_STATIC_URL_TEMPLATE", DEFAULT_URL_TEMPLATE))
    parser.add_argument("--download-dir", type=Path, default=ROOT / "build" / "static-aria2")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--skip-licenses",
        action="store_true",
        default=os.environ.get("ARIA2_SKIP_LICENSE_DOWNLOAD") == "1",
        help="Do not download aria2 license files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.platform_tag:
        raise SystemExit("--platform-tag or ARIA2_WHEEL_PLATFORM_TAG is required")

    name = binary_name(args.platform_tag)
    release = args.release or default_static_release()
    build = static_build_for_platform(args.platform_tag, args.static_build)
    output = args.output or PACKAGE_DIR / "bin" / name
    archive = args.download_dir / f"aria2-{build}_static.zip"
    url = args.url_template.format(release=release, version=release, build=build)

    download_file(url, archive)
    extract_binary(archive, output, name)

    if not args.skip_licenses:
        download_licenses(license_ref_for_release(release), PACKAGE_DIR / "licenses")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
