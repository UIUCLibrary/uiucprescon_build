"""Conan v2 build utilities for building dependencies."""

from __future__ import annotations
import functools
import json
import platform
import pprint
import subprocess  # nosec B404
import shutil
import sys
import tempfile
from typing import (
    AnyStr,
    Callable,
    List,
    Optional,
    TYPE_CHECKING,
    TypedDict,
    TextIO,
)
import os

import conan.errors
import yaml

from uiucprescon.build.compiler_info import get_compiler_version
from uiucprescon.build.conan.files import read_conan_build_info_json

from conan.api.conan_api import ConanAPI
from conan.cli.cli import Cli
from conan.cli.formatters.graph.graph_info_text import filter_graph

import dataclasses

if TYPE_CHECKING:
    from uiucprescon.build.conan_libs import ConanBuildInfo
    from .utils import LanguageStandardsVersion

__all__ = ["build_deps_with_conan"]


@dataclasses.dataclass
class ProfileArg:
    settings_build: Optional[str] = None
    options_build: Optional[str] = None
    conf_build: Optional[str] = None
    profile_host: List[str] = dataclasses.field(default_factory=list)
    build_requires: Optional[str] = None
    settings_host: Optional[str] = None
    options_host: Optional[str] = None
    conf_host: Optional[str] = None
    profile_build: Optional[str] = None


class DependencyMetadata(TypedDict, total=False):
    includedirs: List[str]
    libdirs: List[str]
    bindirs: List[str]
    defines: List[str]
    libs: List[str]


def extract_json_build(fp: TextIO) -> ConanBuildInfo:
    definitions: List[str] = []
    include_paths: List[str] = []
    lib_dirs: List[str] = []
    bin_paths: List[str] = []
    libs: List[str] = []

    data = json.loads(fp.read())
    for node in data["graph"]["nodes"].values():
        if node.get("name") is None:
            continue
        data = node.get("cpp_info", {}).get("root", {})
        include_paths += [
            include_path
            for include_path in data.get("includedirs", []) or []
            if all(
                [
                    include_path not in include_paths,
                    os.path.exists(include_path),
                ]
            )
        ]

        definitions += [
            define
            for define in data.get("defines", []) or []
            if define not in definitions
        ]

        lib_dirs += [
            lib_dir
            for lib_dir in data.get("libdirs", []) or []
            if all([lib_dir not in lib_dirs, os.path.exists(lib_dir)])
        ]

        bin_paths += [
            bindir
            for bindir in data.get("bindirs", []) or []
            if all([bindir not in bin_paths, os.path.exists(bindir)])
        ]

        libs += [lib for lib in data.get("libs", []) or [] if lib not in libs]
    return {
        "definitions": definitions,
        "include_paths": include_paths,
        "lib_paths": lib_dirs,
        "bin_paths": bin_paths,
        "libs": libs,
        "metadata": {},
    }


def _build_deps(
    conan_cache,
    conanfile,
    build_dir,
    build: List[str],
    compiler_version,
    target_os_version,
    compiler_libcxx,
    arch=None,
    language_standards: Optional[LanguageStandardsVersion] = None,
    verbose=False,
    debug=False,
):
    if conanfile is None:
        raise ValueError("conanfile cannot be none")

    conan_api = ConanAPI(
        os.path.abspath(conan_cache) if conan_cache is not None else None
    )
    cli = Cli(conan_api)
    cli.add_commands()
    conan_api.command.run(
        ["profile", "detect", "--exist-ok"]
        + (["-vverbose"] if verbose else [])
    )
    conan_api.reinit()

    build_json = os.path.join(build_dir, "conan_build_info.json")
    conan_args = [
        "install",
        conanfile,
        "--output-folder",
        build_dir,
        "-cc",
        "core:non_interactive=True",
    ] + [f"--build={b}" for b in build]

    if verbose:
        conan_args += ["-c:h", "tools.build:verbosity=verbose"]
        conan_args += ["-c:h", "tools.compilation:verbosity=verbose"]

    if language_standards:
        if language_standards.cpp_std:
            conan_args.append(
                f"--settings:host=compiler.cppstd={language_standards.cpp_std}"
            )

        if language_standards.c_std:
            conan_args.append(
                f"--settings:host=compiler.cstd={language_standards.c_std}"
            )

    if compiler_version:
        conan_args += [
            f"--settings:host=compiler.version={compiler_version}",
        ]
        if platform.system() == "Windows":
            if "MSC" in platform.python_compiler():
                from setuptools.msvc import EnvironmentInfo

                visual_studio_info = EnvironmentInfo("amd64")
                vs_version = int(visual_studio_info.vs_ver)
                conan_args.append(
                    f"--conf=tools.microsoft.msbuild:vs_version={vs_version}"
                )
    if target_os_version:
        conan_args += ["--settings:host", f"os.version={target_os_version}"]

    if compiler_libcxx:
        conan_args += ["--settings:host", f"compiler.libcxx={compiler_libcxx}"]

    if arch:
        conan_args += ["--settings", f"arch={arch}"]
    if debug:
        conan_args += ["--settings", "build_type=Debug"]
    else:
        conan_args += ["--settings", "build_type=Release"]

    conan_args.append("--format=json")
    try:
        result = conan_api.command.run(conan_args)
    except conan.errors.ConanException as e:
        print(
            f'Failed to run conan with: "{" ".join(conan_args)}"',
            file=sys.stderr,
        )
        print("Run with the following environment variables", file=sys.stderr)
        pprint.pprint(dict(sorted(os.environ.items())), stream=sys.stderr)
        raise e
    graph = result["graph"]
    field_filter = result.get("field_filter")
    package_filter = result.get("package_filter")
    serial = graph.serialize()
    serial = filter_graph(
        serial, package_filter=package_filter, field_filter=field_filter
    )
    with open(build_json, "w") as f:
        f.write(json.dumps({"graph": serial}, indent=4))

    return build_json


def locate_cl(paths):
    for path in paths:
        cl = shutil.which("cl.exe", path=path)
        if cl:
            return cl
    raise FileNotFoundError("Unable to locate cl.exe")


def build_msvc_compiler_version_exec(output_exec) -> str:
    from setuptools.msvc import EnvironmentInfo

    visual_studio_info = EnvironmentInfo("amd64")
    cl = locate_cl(visual_studio_info.VCTools)
    with tempfile.TemporaryDirectory() as tempdir:
        test_source_file = os.path.join(tempdir, "get_msvc_version.cpp")

        with open(test_source_file, "w") as f:
            f.write(
                """
#include <stdio.h>
int main(){
    printf("%d\\n", _MSC_VER);
    return 0;
}
""".lstrip()
            )
        env = {**os.environ.copy(), **visual_studio_info.return_env()}
        try:
            out_file = os.path.abspath(output_exec)
            output_path = os.path.dirname(out_file)
            if not os.path.exists(output_path):
                os.makedirs(output_path, exist_ok=True)
            command = [cl, test_source_file, f"/Fe:{out_file}"]
            subprocess.run(  # nosec B603
                command,
                cwd=tempdir,
                env=env,
                check=True,
            )
            return out_file
        except subprocess.CalledProcessError as e:
            print(
                "Failed to compile with MSVC compiler. "
                "Here is the environment complied with."
            )
            pprint.pprint(env)
            print(f"Here is the command that failed: {' '.join(command)}")
            raise e


@functools.cache
def get_msvc_compiler_version(
    working_path: Optional[str] = None, force_rebuild: bool = False
) -> str:
    if working_path is None:
        working_path = tempfile.TemporaryDirectory().name
    exec_file = os.path.join(working_path, "get_msvc_version.exe")

    if not os.path.exists(exec_file) or force_rebuild:
        exec_file = build_msvc_compiler_version_exec(exec_file)
        print(f"Built {exec_file}")

    result = subprocess.run(  # nosec B603
        [exec_file],
        shell=False,
        capture_output=True,
        check=True,
        encoding="mbcs",
        errors="strict",
    )
    try:
        int(result.stdout)
    except ValueError:
        raise ValueError(f"not a valid version: {result.stdout}")
    return result.stdout[:3]


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
    install_libs: bool = True,
    announce: Optional[Callable[[AnyStr, int], None]] = None,
) -> ConanBuildInfo:
    """Build dependencies with conan."""
    if conanfile is None:
        raise ValueError("conanfile cannot be None")
    verbose = False
    settings_yaml = os.path.join(conan_cache, "settings.yml")
    did_settings_yaml_already_exist = os.path.exists(settings_yaml)
    conan_api = ConanAPI(
        os.path.abspath(conan_cache) if conan_cache is not None else None
    )
    if not did_settings_yaml_already_exist:
        with open(settings_yaml, "r") as f:
            settings_data = yaml.load(f.read(), Loader=yaml.SafeLoader)
        default_profile_settings = conan_api.profiles.detect().settings
        default_compiler = default_profile_settings["compiler"]
        settings_data["compiler"][default_compiler]["version"].append(
            default_profile_settings["compiler.version"].value
        )
        settings_data["compiler"][default_compiler]["version"].append(
            get_msvc_compiler_version(working_path=build_dir)
            if default_compiler == "msvc"
            else get_compiler_version()
        )

        with open(settings_yaml, "w") as f:
            yaml.dump(
                settings_data, f, default_flow_style=False, sort_keys=False
            )

    build_json = os.path.join(build_dir, "conan_build_info.json")
    if not os.path.exists(build_json):
        build_json = _build_deps(
            conan_cache,
            conanfile,
            build_dir,
            build,
            compiler_version,
            target_os_version,
            compiler_libcxx,
            arch,
            language_standards,
            verbose,
            debug,
        )
    with open(build_json, "r", encoding="utf-8") as f:
        build_info = read_conan_build_info_json(f)

    return build_info
