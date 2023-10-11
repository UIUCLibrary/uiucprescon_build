from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from conans.client.cache.cache import ClientCache
from conan.api.conan_api import ConanAPI
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
) -> ConanBuildInfo:
    def run(conan_path):
        conan_api = ConanAPI()
        remotes = conan_api.remotes.list()
        profile_host = conan_api.profiles.detect()
        profile_host.process_settings(ClientCache(conan_path))

        profile_build = conan_api.profiles.detect()
        profile_build.process_settings(ClientCache(conan_path))

        deps_graph = conan_api.graph.load_graph_consumer(
            path=conanfile,
            name="CompressorRecipe",
            version="123",
            user="args.user",
            channel="args.channel",
            profile_host=profile_host,
            profile_build=profile_build,
            lockfile=None,
            remotes=remotes,
            update=False,
            is_build_require=False
        )
        conan_api.graph.analyze_binaries(
            deps_graph,
            build_mode=["missing"],
            remotes=remotes
        )
        conan_api.install.install_binaries(deps_graph, remotes)
        data = {}
        for dep in deps_graph.root.dependencies:
            conan_file = dep.dst.conanfile
            data = {**data, **conan_file.cpp_info.serialize()}
        return data
    data = run(conan_cache)

    definitions = []
    libs = []
    include_paths = []
    lib_paths = []
    bin_paths = []
    for dep in data.values():
        include_paths += dep['includedirs']
        lib_paths += dep['libdirs']
        bin_paths += dep['bindirs']
        if dep['defines'] is not None:
            definitions += dep['defines']
        libs += dep['libs']
    return {
        "definitions": definitions,
        "include_paths": include_paths,
        "lib_paths": lib_paths,
        "bin_paths": bin_paths,
        "libs": libs,
        "metadata": {}
    }
