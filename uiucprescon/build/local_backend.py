import os

import setuptools.build_meta
import platform
from . import conan_libs
from . import monkey
from pathlib import Path
from typing import Optional, Dict, List, Union, cast

pyproj_toml = Path("pyproject.toml")


def build_sdist(
    sdist_directory: str,
    config_settings: Optional[Dict[str, Union[str, List[str], None]]] = None,
) -> str:
    return setuptools.build_meta.build_sdist(sdist_directory, config_settings)


def build_wheel(
    wheel_directory: str,
    config_settings: Optional[Dict[str, Union[str, List[str], None]]] = None,
    metadata_directory: Optional[str] = None,
) -> str:
    if platform.system() == "Windows":
        monkey.patch_for_msvc_specialized_compiler()

    if (
        config_settings is not None
        and config_settings.get("conan_cache") is not None
        and "CONAN_USER_HOME" in os.environ
    ):
        config_settings["conan_cache"] = os.path.join(
            os.environ["CONAN_USER_HOME"], ".conan"
        )
    conan_libs.build_conan(
        wheel_directory,
        config_settings,
        metadata_directory,
        install_libs=False,
    )
    original_conan_user_home = os.getenv("CONAN_USER_HOME")

    try:
        if config_settings is not None and "conan_cache" in config_settings:
            os.environ["CONAN_USER_HOME"] = os.path.normpath(
                os.path.join(cast(str, config_settings["conan_cache"]), "..")
            )

        return setuptools.build_meta.build_wheel(
            wheel_directory, config_settings, metadata_directory
        )

    finally:
        if original_conan_user_home:
            os.environ["CONAN_USER_HOME"] = original_conan_user_home
        else:
            try:
                os.unsetenv("CONAN_USER_HOME")
            except AttributeError:
                pass


def get_requires_for_build_sdist(
    config_settings: Optional[Dict[str, Union[str, List[str], None]]] = None,
) -> List[str]:
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: Optional[Dict[str, Union[str, List[str], None]]] = None,
) -> str:
    return setuptools.build_meta.prepare_metadata_for_build_wheel(
        metadata_directory, config_settings
    )


def get_requires_for_build_wheel(
    config_settings: Optional[Dict[str, Union[str, List[str], None]]] = None,
) -> List[str]:
    return ["wheel >= 0.25", "setuptools", "pybind11>=2.5", "toml"]


def build_editable(
    wheel_directory: Union[str, os.PathLike[str]],
    config_settings: Union[
        Dict[str, Union[str, List[str], None]], None
    ] = None,
    metadata_directory: Optional[str] = None,
):
    return setuptools.build_meta.build_editable(
        wheel_directory, config_settings, metadata_directory
    )
