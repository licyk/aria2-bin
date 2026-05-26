from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.build_wheel import build_wheel_from_config, prepare_metadata  # noqa: E402


def get_requires_for_build_wheel(config_settings=None):
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    return prepare_metadata(Path(metadata_directory))


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    return build_wheel_from_config(Path(wheel_directory), config_settings or {})
