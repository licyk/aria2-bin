from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def binary_path() -> Path:
    exe_name = "aria2c.exe" if os.name == "nt" else "aria2c"
    return Path(__file__).resolve().parent / "bin" / exe_name


def main() -> int:
    exe = binary_path()
    if not exe.exists():
        sys.stderr.write(f"aria2c executable is missing from wheel: {exe}\n")
        return 127
    if os.name != "nt" and not os.access(exe, os.X_OK):
        try:
            exe.chmod(exe.stat().st_mode | 0o111)
        except OSError:
            pass
    try:
        return subprocess.call([str(exe), *sys.argv[1:]])
    except PermissionError:
        sys.stderr.write(f"aria2c executable is not runnable: {exe}\n")
        return 126


if __name__ == "__main__":
    raise SystemExit(main())
