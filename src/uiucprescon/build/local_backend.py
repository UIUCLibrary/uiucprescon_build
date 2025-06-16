import contextlib
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


@contextlib.contextmanager
def set_env_var(env_vars: Dict[str, str]):
    """Set an environment variable."""
    og = os.environ.copy()
    try:
        os.environ.update(env_vars)
        yield
    finally:
        os.environ = og


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
    env_vars = {}
    if config_settings is not None:
        if "conan_cache" in config_settings:
            env_vars["CONAN_USER_HOME"] = os.path.normpath(
                os.path.join(cast(str, config_settings["conan_cache"]), "..")
            )
        if "target_os_version" in config_settings:
            if platform.system() == "Darwin":
                env_vars["MACOSX_DEPLOYMENT_TARGET"] =\
                    config_settings["target_os_version"]
    with set_env_var(env_vars):
        return setuptools.build_meta.build_wheel(
            wheel_directory, config_settings, metadata_directory
        )


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
