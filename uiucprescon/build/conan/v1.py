"""Version 1 of conan api.

This was written before conan has a stable Python API which was introduced in
version 2. This code only works with Conan version 1 because it calls on code
that was removed from conan in version 2.
"""

import logging
import os
import sys
import re
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, cast

from conans.client import conan_api, conf   # pylint: disable=import-error

from uiucprescon.build.utils import locate_file
from uiucprescon.build.compiler_info import (  # pylint: disable=import-error
    get_compiler_name
)
from .files import ConanBuildInfoTXT

__all__ = ['build_deps_with_conan']


def build_deps_with_conan(
        conanfile: str,
        build_dir: str,
        install_dir: str,
        compiler_libcxx: str,
        compiler_version: str,
        conan_cache: Optional[str] = None,
        conan_options: Optional[List[str]] = None,
        debug: bool = False,
        install_libs=True,
        build=None,
        announce=None
):

    conan = conan_api.Conan(
        cache_folder=os.path.abspath(conan_cache) if conan_cache else None
    )
    settings = []
    logger = logging.Logger(__name__)
    conan_profile_cache = os.path.join(build_dir, "profiles")
    build = build or ['outdated']
    for name, value in conf.detect.detect_defaults_settings(
            logger,
            conan_profile_cache
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
            if 'compiler.libcxx=libstdc' in settings:
                settings.remove('compiler.libcxx=libstdc')
            settings.append(f'compiler.libcxx={compiler_libcxx}')
        settings.append(f"compiler.version={compiler_version}")
        if compiler_name == 'gcc':
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

    conanfile_path = os.path.abspath('.')

    ninja = shutil.which("ninja")
    env = []
    if ninja:
        env.append(f"NINJA={ninja}")

    profile_host = conan_api.ProfileData(
        profiles=None,
        settings=settings,
        options=None,
        env=env,
        conf=None
    )
    conan.install(
        options=conan_options,
        cwd=os.path.abspath(build_dir),
        settings=settings,
        profile_build=profile_host,
        build=build if len(build) > 0 else None,
        path=conanfile_path,
        env=env,
        no_imports=not install_libs,
    )

    if install_libs:
        import_manifest = os.path.join(
            build_dir,
            'conan_imports_manifest.txt'
        )
        if os.path.exists(import_manifest):
            add_conan_imports(
                import_manifest,
                path=build_dir,
                dest=install_dir
            )
#
    conaninfotext = os.path.join(build_dir, "conaninfo.txt")
    if os.path.exists(conaninfotext) and announce:
        with open(conaninfotext, "r", encoding="utf-8") as r:
            announce(r.read(), 5)
    build_locations = [
        build_dir,
        os.path.join(build_dir, "Release")
    ]
    conanbuildinfotext =\
        locate_file("conanbuildinfo.txt", build_locations)

    if conanbuildinfotext is None:
        raise AssertionError("Missing conanbuildinfo.txt")
    metadata_strategy = ConanBuildInfoTXT()
    metadata_strategy.parse(conanbuildinfotext)


def fixup_library(shared_library: str) -> None:
    if sys.platform == "darwin":
        otool = shutil.which("otool")
        install_name_tool = shutil.which('install_name_tool')
        if not all([otool, install_name_tool]):
            raise FileNotFoundError(
                "Unable to fixed up because required tools are missing. "
                "Make sure that otool and install_name_tool are on "
                "the PATH."
            )

        # Hack: Casting the following to strings to help MyPy which doesn't
        #  currently (as of mypy version 1.6.0) understand that if they any
        #  were None, they'd raise a FileNotFound error.
        otool = cast(str, otool)
        install_name_tool = cast(str, install_name_tool)

        dylib_regex = re.compile(
            r'^(?P<path>([@a-zA-Z./_])+)'
            r'/'
            r'(?P<file>lib[a-zA-Z/.0-9]+\.dylib)'
        )
        for line in subprocess.check_output(
                [otool, "-L", shared_library],
                encoding="utf8"
        ).split("\n"):
            if any(
                    [
                        line.strip() == "",  # it's an empty line
                        str(shared_library) in line,  # it's the same library
                        "/usr/lib/" in line,  # it's a system library

                    ]
            ):
                continue
            value = dylib_regex.match(line.strip())
            if value:
                try:
                    original_path = value.group("path")
                    library_name = value["file"].strip()
                except AttributeError as e:
                    raise ValueError(f"unable to parse {line}") from e
            else:
                raise ValueError(f"unable to parse {line}")

            command = [
                install_name_tool,
                "-change",
                os.path.join(original_path, library_name),
                os.path.join("@loader_path", library_name),
                str(shared_library)
            ]
            subprocess.check_call(command)


def add_conan_imports(import_manifest_file: str, path: str, dest: str) -> None:
    libs = []
    with open(import_manifest_file, "r", encoding="utf8") as f:
        for line in f.readlines():
            if ":" not in line:
                continue

            try:
                file_name, _ = line.strip().split(": ")
            except ValueError:
                print(f"Failed to parse: {line.strip()}")
                raise
            libs.append(file_name)
    for file_name in libs:
        file_path = Path(os.path.join(path, file_name))
        if not file_path.exists():
            raise FileNotFoundError(f"Missing {file_name}")
        lib = str(file_path)
        fixup_library(lib)
        output = Path(os.path.join(dest, file_path.name))
        if output.exists():
            output.unlink()
        shutil.copy(file_path, dest, follow_symlinks=False)
        if file_path.is_symlink():
            continue
