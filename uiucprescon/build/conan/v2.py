from __future__ import annotations
from typing import (
    AnyStr,
    Callable,
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    TypedDict,
)
import os

try:
    from conan.api.conan_api import ConanAPI
except ImportError as error:
    raise ImportError("conan 2.0 api not found.") from error

import dataclasses

if TYPE_CHECKING:
    from uiucprescon.build.conan_libs import ConanBuildInfo


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


def build_deps_with_conan(
    conanfile: str,
    build_dir: str,
    install_dir: str,
    compiler_libcxx: str,
    compiler_version: str,
    conan_cache: Optional[str] = None,
    conan_options: Optional[List[str]] = None,
    debug: bool = False,
    install_libs: bool = True,
    build=None,
    announce: Optional[Callable[[AnyStr, int], None]] = None,
) -> ConanBuildInfo:
    conan_path = conan_cache
    conan_api = ConanAPI(
        os.path.abspath(conan_cache) if conan_cache is not None else None
    )
    remotes = conan_api.remotes.list()
    profile_host = conan_api.profiles.detect()
    profile_host.process_settings(conan_api.config.settings_yml)

    profile_build = conan_api.profiles.detect()
    profile_build.process_settings(conan_api.config.settings_yml)

    root_node = conan_api.graph._load_root_consumer_conanfile(
        conanfile, profile_host, profile_build
    )
    deps_graph = conan_api.graph.load_graph(
        root_node, profile_build=profile_build, profile_host=profile_host
    )

    conan_api.graph.analyze_binaries(
        deps_graph, build_mode=["missing"], remotes=remotes
    )
    conan_api.install.install_binaries(deps_graph, remotes)
    data: Dict[str, DependencyMetadata] = {}
    for dep in deps_graph.root.dependencies:
        conan_file = dep.dst.conanfile
        data = {**data, **conan_file.cpp_info.serialize()}

    return extract_metadata(data)


def extract_metadata(data: Dict[str, DependencyMetadata]) -> ConanBuildInfo:
    definitions = []
    libs = []
    include_paths = []
    lib_paths = []
    bin_paths = []
    for dep in data.values():
        include_paths += dep["includedirs"]
        lib_paths += dep["libdirs"]
        bin_paths += dep["bindirs"]
        if dep["defines"] is not None:
            definitions += dep["defines"]
        libs += dep["libs"]
    return {
        "definitions": definitions,
        "include_paths": include_paths,
        "lib_paths": lib_paths,
        "bin_paths": bin_paths,
        "libs": libs,
        "metadata": {},
    }
