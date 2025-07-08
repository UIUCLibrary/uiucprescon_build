"""Version 1 of conan api.

This was written before conan has a stable Python API which was introduced in
version 2. This code only works with Conan version 1 because it calls on code
that was removed from conan in version 2.
"""
from __future__ import annotations
import logging
import os
import platform
import shutil
from typing import List, Optional, TYPE_CHECKING

from conans.client import conan_api, conf  # pylint: disable=import-error

from uiucprescon.build.utils import locate_file
from uiucprescon.build.compiler_info import (  # pylint: disable=import-error
    get_compiler_name,
    get_compiler_version,
)
from .files import ConanBuildInfoTXT
from .utils import copy_conan_imports_from_manifest

if TYPE_CHECKING:
    from .utils import LanguageStandardsVersion

__all__ = ["build_deps_with_conan"]


def build_deps_with_conan(
    conanfile: str,
    build_dir: str,
    install_dir: str,
    compiler_libcxx: str,
    compiler_version: str,
    build: List[str],
    conan_cache: Optional[str] = None,
    conan_options: Optional[List[str]] = None,
    target_os_version: Optional[str] = None,
    arch: Optional[str] = None,
    language_standards: Optional[LanguageStandardsVersion] = None,
    debug: bool = False,
    install_libs=True,
    announce=None,
):
    conan = conan_api.Conan(
        cache_folder=os.path.abspath(conan_cache) if conan_cache else None
    )
    settings_yaml = os.path.join(conan.cache_folder, "settings.yml")
    if not os.path.exists(settings_yaml):
        # This can be updated
        import yaml

        # This is a hack to create the settings.yml file
        conan.config_get("storage.path")

        # This has the site effect for generating the settings.yml file
        conan.app.cache.settings.copy()
        with open(settings_yaml, "r") as f:
            settings_data = yaml.load(f.read(), Loader=yaml.SafeLoader)

        default_compiler = conan.app.cache.default_profile.settings["compiler"]
        settings_data["compiler"][default_compiler]["version"].append(
            conan.app.cache.default_profile.settings["compiler.version"]
        )
        settings_data["compiler"][default_compiler]["version"].append(
            get_compiler_version()
        )

        with open(settings_yaml, "w") as f:
            yaml.dump(
                settings_data, f, default_flow_style=False, sort_keys=False
            )

    settings = []
    logger = logging.Logger(__name__)
    conan_profile_cache = os.path.join(build_dir, "profiles")
    build = build or ["outdated"]
    for name, value in conf.detect.detect_defaults_settings(
        logger, conan_profile_cache
    ):
        settings.append(f"{name}={value}")
    if debug is True:
        settings.append("build_type=Debug")
    else:
        settings.append("build_type=Release")
    try:
        compiler_name = get_compiler_name()
        settings.append(f"compiler={compiler_name}")
        if compiler_libcxx is not None:
            if "compiler.libcxx=libstdc" in settings:
                settings.remove("compiler.libcxx=libstdc")
            settings.append(f"compiler.libcxx={compiler_libcxx}")
        settings.append(f"compiler.version={compiler_version}")
        if compiler_name == "gcc":
            pass
        elif compiler_name == "msvc":
            settings.append("compiler.cppstd=14")
            settings.append("compiler.runtime=dynamic")
        elif compiler_name == "Visual Studio":
            settings.append("compiler.runtime=MD")
            settings.append("compiler.toolset=v142")
    except AttributeError:
        print(
            f"Unable to get compiler information "
            f"for {platform.python_compiler()}"
        )
        raise

    ninja = shutil.which("ninja")
    env = []
    if ninja:
        env.append(f"NINJA={ninja}")

    profile_host = conan_api.ProfileData(
        profiles=None, settings=settings, options=None, env=env, conf=None
    )
    conan.install(
        options=conan_options,
        cwd=os.path.abspath(build_dir),
        settings=settings,
        profile_build=profile_host,
        build=build if len(build) > 0 else None,
        path=os.path.abspath(conanfile),
        env=env,
        no_imports=not install_libs,
    )

    if install_libs:
        import_manifest = os.path.join(build_dir, "conan_imports_manifest.txt")
        if os.path.exists(import_manifest):
            copy_conan_imports_from_manifest(
                import_manifest, path=build_dir, dest=install_dir
            )
    #
    conaninfotext = os.path.join(build_dir, "conaninfo.txt")
    if os.path.exists(conaninfotext) and announce:
        with open(conaninfotext, "r", encoding="utf-8") as r:
            announce(r.read(), 5)
    build_locations = [build_dir, os.path.join(build_dir, "Release")]
    conanbuildinfotext = locate_file("conanbuildinfo.txt", build_locations)

    if conanbuildinfotext is None:
        raise AssertionError("Missing conanbuildinfo.txt")
    metadata_strategy = ConanBuildInfoTXT()
    return metadata_strategy.parse(conanbuildinfotext)
