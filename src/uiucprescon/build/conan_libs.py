from __future__ import annotations
import functools
import io
import os
import platform
import re
import subprocess  # nosec B404
import sys
import shutil
import abc
from importlib.metadata import version
import typing
from typing import Dict, List, Optional, cast, Set, Tuple, Union, TYPE_CHECKING
import warnings

from pathlib import Path
import json
import toml

import setuptools
from setuptools.dist import Distribution
from setuptools.command.build_ext import build_ext as BuildExt
from setuptools.command.build_py import build_py as BuildPy
from setuptools.command.build_clib import build_clib as BuildClib
from setuptools.command.build import build as Build

from uiucprescon.build.deps import get_win_deps
from uiucprescon.build.compiler_info import (
    get_compiler_version,
)
from uiucprescon.build.conan import conan_api
from uiucprescon.build.conan.files import (
    ConanBuildInfo,
    read_conan_build_info_json,
    parse_conan_build_info,
    get_library_metadata_from_build_info_json,
    get_linking_libraries_fp
)
from uiucprescon.build.conan.utils import LanguageStandardsVersion

if TYPE_CHECKING:
    import distutils.ccompiler


class AbsConanBuildInfo(abc.ABC):
    @abc.abstractmethod
    def parse(self, filename: str) -> Dict[str, str]:
        pass


class AbsResultTester(abc.ABC):
    def __init__(
        self, compiler: Optional[distutils.ccompiler.CCompiler] = None
    ) -> None:
        self.compiler = compiler or self._get_compiler()

    @staticmethod
    def _get_compiler():
        build_ext = setuptools.Distribution().get_command_obj("build_ext")
        build_ext.finalize_options()
        build_ext.extensions = [setuptools.Extension("ignored", ["ignored.c"])]
        build_ext.build_extensions = lambda: None
        build_ext.run()
        return build_ext.compiler

    def test_shared_libs(self, libs_dir: str) -> None:
        """Make sure all shared libraries in directory are linked"""

        for lib in os.scandir(libs_dir):
            if not lib.name.endswith(self.compiler.shared_lib_extension):
                continue
            self.test_binary_dependents(Path(lib.path))

    @abc.abstractmethod
    def test_binary_dependents(self, file_path: Path) -> None:
        """Make sure shared library is linked"""


class MacResultTester(AbsResultTester):
    def test_binary_dependents(self, file_path: Path) -> None:
        otool = shutil.which("otool")
        if otool is None:
            raise FileNotFoundError("otool")
        self.compiler.spawn([otool, "-L", str(file_path.resolve())])


class WindowsResultTester(AbsResultTester):
    def test_binary_dependents(self, file_path: Path) -> None:
        deps = get_win_deps(
            str(file_path.resolve()),
            output_file=f"{file_path.stem}.depends",
            compiler=self.compiler,
        )

        system_path = os.getenv("PATH")
        if system_path is None:
            raise ValueError("PATH variable not set")
        for dep in deps:
            print(f"{file_path} requires {dep}")
            locations = list(filter(os.path.exists, system_path.split(";")))
            locations.append(str(file_path.parent.absolute()))
            for location in locations:
                dep_path = os.path.join(location, dep)
                if os.path.exists(dep_path):
                    print(f"Found requirement: {dep_path}")
                    break
            else:
                print(f"Couldn't find {dep}")


class LinuxResultTester(AbsResultTester):
    def test_binary_dependents(self, file_path: Path):
        ldd = shutil.which("ldd")
        if ldd is None:
            raise FileNotFoundError("ldd not found")
        self.compiler.spawn([ldd, str(file_path.resolve())])


class CompilerInfoAdder:
    def __init__(
        self, build_ext_cmd: setuptools.command.build_ext.build_ext
    ) -> None:
        super().__init__()
        self._build_ext_cmd = build_ext_cmd
        if build_ext_cmd.compiler is None:
            self._place_to_add = build_ext_cmd
        else:
            self._place_to_add = build_ext_cmd.compiler

    def add_libs(self, libs: List[str]) -> None:
        extension_deps: Set[str] = set()
        for lib in reversed(libs):
            if (
                lib not in self._place_to_add.libraries
                and lib not in extension_deps
            ):
                extension_deps.add(lib)
                self._place_to_add.libraries.insert(0, lib)

    def add_lib_dirs(self, lib_dirs: List[str]) -> None:
        for path in reversed(lib_dirs):
            if not os.path.exists(path):
                raise FileNotFoundError(f"{path} does not exist")
            if path not in self._place_to_add.library_dirs:
                self._place_to_add.library_dirs.insert(0, path)

    def add_include_dirs(self, include_dirs: List[str]) -> None:
        for path in reversed(include_dirs):
            if path not in self._place_to_add.include_dirs:
                self._place_to_add.include_dirs.insert(0, path)
            else:
                self._place_to_add.compiler.include_dirs.insert(0, path)


class ConanBuildMetadata:
    def __init__(self, filename: str) -> None:
        super().__init__()
        self.filename = filename
        with open(self.filename, "r", encoding="utf-8") as f:
            self._data = json.loads(f.read())

    def deps(self) -> List[Dict[str, str]]:
        return [a["name"] for a in self._data["dependencies"]]

    def dep(self, dep: str) -> Dict[str, str]:
        deps = self._data["dependencies"]
        return [d for d in deps if d["name"] == dep][0]


def update_extension(
    extension: setuptools.extension.Extension, metadata: ConanBuildMetadata
) -> None:
    updated_libs: List[str] = []
    include_dirs: List[str] = []
    library_dirs: List[str] = []
    define_macros: List[Tuple[str, Union[str, None]]] = []
    for extension_lib in extension.libraries:
        if extension_lib in metadata.deps():
            dep_metadata = metadata.dep(extension_lib)
            updated_libs += dep_metadata.get("libs", [])
            include_dirs += dep_metadata.get("include_paths", [])
            library_dirs += dep_metadata.get("lib_paths", [])
            define_macros += [
                (d, None) for d in dep_metadata.get("definitions", [])
            ]
        else:
            updated_libs.append(extension_lib)
    extension.libraries = updated_libs
    extension.include_dirs = include_dirs + extension.include_dirs
    extension.library_dirs = library_dirs + extension.library_dirs
    extension.define_macros = define_macros + extension.define_macros


def update_extension3(
    extension: setuptools.extension.Extension,
    strategy: typing.Callable[[setuptools.extension.Extension], None]
) -> None:
    strategy(extension)


def match_libs(
    extension: setuptools.extension.Extension,
    build_path: str
) -> None:
    build_json = os.path.join(build_path, "conan_build_info.json")

    with open(build_json, "r", encoding="utf-8") as f:
        libraries = extension.libraries.copy()
        for original_lib_name in libraries:
            if metadata := get_library_metadata_from_build_info_json(
                original_lib_name,
                f
            ):
                # replace name of the library in case the actual name is
                # different from the original
                new_names = update_library_names(original_lib_name, f)
                if len(new_names) > 0 \
                    and (
                        len(new_names) > 1 or new_names[0] != original_lib_name
                ):
                    original_position =\
                        extension.libraries.index(original_lib_name)
                    extension.libraries.remove(original_lib_name)
                    for new_name in reversed(new_names):
                        extension.libraries.insert(original_position, new_name)

                extension.libraries += [
                    lib for lib in metadata.libs
                    if lib not in extension.libraries
                ]

                for include_path in reversed(metadata.include_paths):
                    if include_path not in extension.include_dirs:
                        extension.include_dirs.insert(0, include_path)

                for lib_path in reversed(metadata.lib_dirs):
                    if lib_path not in extension.library_dirs:
                        extension.library_dirs.insert(0, lib_path)

                for define_macro in reversed(metadata.definitions):
                    if define_macro not in extension.define_macros:
                        extension.define_macros.insert(0, define_macro)


def add_all_libs(
    extension: setuptools.extension.Extension,
    text_md: ConanBuildInfo
) -> None:
    """
    This strategy adds all libraries from the extension to the extension's
    libraries list.
    """
    include_dirs = text_md["include_paths"]
    library_dirs = text_md["lib_paths"]
    define_macros = [(d, None) for d in text_md.get("definitions", [])]
    libs = extension.libraries.copy()

    for original_lib_name in extension.libraries:
        metadata = text_md["metadata"]
        if original_lib_name not in metadata:
            continue
        conan_libs = metadata[original_lib_name]["libs"]
        index = libs.index(original_lib_name)
        libs[index: index + 1] = conan_libs

    extension.libraries = libs
    for lib in text_md["libs"]:
        if lib not in extension.libraries:
            extension.libraries.append(lib)

    extension.include_dirs = include_dirs + extension.include_dirs
    extension.library_dirs = library_dirs + extension.library_dirs
    extension.define_macros = define_macros + extension.define_macros


def update_extension2(
    extension: setuptools.extension.Extension, text_md: ConanBuildInfo
) -> None:
    include_dirs = text_md["include_paths"]
    library_dirs = text_md["lib_paths"]
    define_macros = [(d, None) for d in text_md.get("definitions", [])]
    libs = extension.libraries.copy()

    for original_lib_name in extension.libraries:
        metadata = text_md["metadata"]
        if original_lib_name not in metadata:
            continue
        conan_libs = metadata[original_lib_name]["libs"]
        index = libs.index(original_lib_name)
        libs[index: index + 1] = conan_libs

    extension.libraries = libs
    for lib in text_md["libs"]:
        if lib not in extension.libraries:
            extension.libraries.append(lib)

    extension.include_dirs = include_dirs + extension.include_dirs
    extension.library_dirs = library_dirs + extension.library_dirs
    extension.define_macros = define_macros + extension.define_macros


def get_conan_options() -> List[str]:
    pyproject_toml_data = get_pyproject_toml_data()
    if "localbuilder" not in pyproject_toml_data:
        return []

    local_builder_settings = pyproject_toml_data["localbuilder"]
    platform_settings = local_builder_settings.get(sys.platform)
    if platform_settings is None:
        return []
    return platform_settings.get("conan_options", [])


class BuildConan(setuptools.Command):
    user_options = [
        ("conan-cache=", None, "conan cache directory"),
        ("compiler-version=", None, "Compiler version"),
        ("compiler-libcxx=", None, "Compiler libcxx"),
        ("target-os-version=", None, "Target OS version"),
    ]

    description = "Get the required dependencies from a Conan package manager"

    def initialize_options(self) -> None:
        self.conan_cache: Optional[str] = None
        self.compiler_version: Optional[str] = None
        self.compiler_libcxx: Optional[str] = None
        self.target_os_version: Optional[str] = None
        self.build_libs: List[str] = ["missing"]
        self.conanfile: Optional[str] = None
        self.arch = None
        self.build_temp: Optional[str] = None
        self.language_standards = None

    def __init__(self, dist: setuptools.dist.Distribution, **kw: str) -> None:
        self.install_libs = True
        self.build_libs = []
        super().__init__(dist, **kw)

    def finalize_options(self) -> None:
        build_cmd = cast(Build, self.get_finalized_command("build"))

        self.conan_home = os.path.join(build_cmd.build_base, "conan")
        if not os.path.exists(self.conan_home):
            self.mkpath(self.conan_home)

        self.build_temp = os.path.join(build_cmd.build_temp, "conan_build")
        if not os.path.exists(self.build_temp):
            self.mkpath(self.build_temp)

        if self.conan_cache is None:
            if version("conan") < "2.0.0":
                self.conan_cache = os.path.join(
                    os.environ.get("CONAN_USER_HOME", self.conan_home),
                    ".conan"
                )
            else:
                self.conan_cache = os.path.join(
                    os.environ.get("CONAN_USER_HOME", self.conan_home),
                    ".conan2"
                )

        if self.compiler_libcxx is None:
            self.compiler_libcxx = os.getenv("CONAN_COMPILER_LIBCXX")

        if self.compiler_version is None:
            # This function section is ugly and should be refactored
            if version("conan") < "2.0.0":
                self.compiler_version = os.getenv(
                    "CONAN_COMPILER_VERSION", get_compiler_version()
                )
            else:
                if platform.system() == "Windows":
                    if "msc" in platform.python_compiler().lower():
                        from .conan.v2 import get_msvc_compiler_version
                        self.compiler_version =\
                            get_msvc_compiler_version(self.build_temp)

    def getConanBuildInfo(
        self, root_dir: str
    ) -> Optional[str]:  # pragma: no cover
        warnings.warn("Don't use", DeprecationWarning)
        for root, _, files in os.walk(root_dir):
            for f in files:
                if f == "conanbuildinfo.json":
                    return os.path.join(root, f)
        return None

    def add_deps_to_compiler(self, metadata) -> None:
        build_ext_cmd = cast(BuildExt, self.get_finalized_command("build_ext"))
        compiler_adder = CompilerInfoAdder(build_ext_cmd)

        include_dirs = metadata["include_paths"]
        compiler_adder.add_include_dirs(include_dirs)
        self.announce(
            f"Added the following paths to include "
            f"path {', '.join(include_dirs)} ",
            5,
        )

        lib_paths = metadata["lib_paths"]

        compiler_adder.add_lib_dirs(lib_paths)
        self.announce(
            f"Added the following paths to library "
            f"path {', '.join(metadata['lib_paths'])} ",
            5,
        )

        for extension in build_ext_cmd.extensions:
            for lib in metadata["libs"]:
                if lib not in extension.libraries:
                    extension.libraries.append(lib)

    def run(self) -> None:
        build_ext = cast(BuildExt, self.get_finalized_command("build_ext"))
        if self.install_libs:
            if build_ext._inplace:
                install_dir = os.path.abspath(build_ext.build_temp)
            else:
                build_py = cast(
                    BuildPy, self.get_finalized_command("build_py")
                )
                if len(build_py.packages) == 0:
                    install_dir = build_py.build_lib
                else:
                    install_dir = os.path.abspath(
                        os.path.join(
                            build_py.build_lib,
                            build_py.get_package_dir(build_py.packages[0]),
                        )
                    )
        else:
            install_dir = build_ext.build_temp

        build_dir_full_path = os.path.abspath(self.build_temp)
        conan_cache = self.conan_cache
        if conan_cache and not os.path.exists(conan_cache):
            self.mkpath(conan_cache)
            self.announce(f"Created {conan_cache} for conan cache", 5)
        if not os.path.exists(build_dir_full_path):
            self.mkpath(build_dir_full_path)
        self.announce(f"Using {conan_cache} for conan cache", 5)
        conanfile = (
            self.conanfile or
            _find_conanfile(path=".") or
            os.path.abspath(".")
        )
        metadata = build_deps_with_conan(
            conanfile=conanfile,
            build_dir=self.build_temp,
            install_dir=os.path.abspath(install_dir),
            compiler_libcxx=self.compiler_libcxx,
            compiler_version=self.compiler_version,
            target_os_version=self.target_os_version,
            arch=self.arch,
            build=self.build_libs if len(self.build_libs) > 0 else None,
            language_standards=self.language_standards,
            conan_options=get_conan_options(),
            conan_cache=conan_cache,
            install_libs=self.install_libs,
            announce=self.announce,
        )
        build_ext_cmd = cast(BuildExt, self.get_finalized_command("build_ext"))
        extensions = []
        for extension in build_ext_cmd.extensions:
            if build_ext._inplace:
                extension.runtime_library_dirs.append(
                    os.path.abspath(install_dir)
                )
            update_extension3(
                extension,
                strategy=(
                    functools.partial(add_all_libs, text_md=metadata)
                    if version("conan") < "2.0.0" else
                    functools.partial(match_libs, build_path=self.build_temp)
                )
            )
            extension.library_dirs.insert(0, install_dir)
            if sys.platform == "darwin":
                extension.runtime_library_dirs.append("@loader_path")
            elif sys.platform == "linux":
                if "$ORIGIN" not in extension.runtime_library_dirs:
                    extension.runtime_library_dirs.append("$ORIGIN")
            extensions.append(extension)
        build_ext_cmd.extensions = extensions


def _get_source_root(dist: Distribution) -> str:
    project_files = ["pyproject.toml", "setup.py"]
    path = dist.src_root or os.curdir
    for project_file in project_files:
        project_file_path = Path(path, project_file)
        if os.path.exists(project_file_path):
            return os.path.abspath(path)
    return os.path.abspath(path)


def _find_conanfile(path: str) -> Optional[str]:
    conanfile_types = ["conanfile.py", "conanfile.txt"]
    for conanfile_type in conanfile_types:
        conanfile = os.path.join(path, conanfile_type)
        if os.path.exists(conanfile):
            return conanfile
    return None


def build_conan(
    wheel_directory: str,
    config_settings: Optional[Dict[str, Union[str, List[str], None]]] = None,
    metadata_directory: Optional[str] = None,
    install_libs: bool = True,
) -> None:
    dist = Distribution()
    dist.parse_config_files()

    source_root = _get_source_root(dist)

    command = BuildConan(dist)
    command.conanfile = _find_conanfile(path=source_root)
    if metadata_directory is not None:
        build_py = cast(BuildPy, command.get_finalized_command("build_py"))
        build_py.build_lib = wheel_directory

        build_ext = cast(BuildExt, command.get_finalized_command("build_ext"))
        build_ext.build_temp = wheel_directory

        build_clib = cast(
            BuildClib, command.get_finalized_command("build_clib")
        )
        build_clib.build_temp = wheel_directory

    command.install_libs = install_libs
    conan_cache = None

    if config_settings:
        conan_cache = config_settings.get("conan_cache")
        command.conan_cache = conan_cache

        command.target_os_version = config_settings.get("target_os_version")
        if not command.target_os_version:
            command.target_os_version = os.getenv("MACOSX_DEPLOYMENT_TARGET")

        command.compiler_libcxx = config_settings.get("conan_compiler_libcxx")
        command.arch = config_settings.get("arch")
        if version("conan") > "2.0.0" and "MSC" in platform.python_compiler():
            from uiucprescon.build.conan.v2 import get_msvc_compiler_version
            command.compiler_version = get_msvc_compiler_version()
        else:
            command.compiler_version = config_settings.get(
                "conan_compiler_version", get_compiler_version()
            )
        if version("conan") > "2.0.0":
            command.language_standards = LanguageStandardsVersion(
                cpp_std=config_settings.get("cxx_std")
            )

    if conan_cache is None:
        conan_home = os.getenv("CONAN_USER_HOME")
        if conan_home is not None:
            if version("conan") < "2.0.0":
                conan_cache = os.path.join(conan_home, ".conan")
            else:
                conan_cache = os.path.join(conan_home, ".conan2")

    if conan_cache is None:
        if version("conan") < "2.0.0":
            os.path.join(
                cast(
                    BuildExt, command.get_finalized_command("build_ext")
                ).build_temp,
                ".conan",
            )
        else:
            os.path.join(
                cast(
                    BuildExt, command.get_finalized_command("build_ext")
                ).build_temp,
                ".conan2",
            )
    command.finalize_options()
    command.run()


def get_pyproject_toml_data() -> Dict[str, typing.Any]:
    pyproj_toml = Path("pyproject.toml")
    with open(pyproj_toml, "r", encoding="utf-8") as f:
        return toml.load(f)


def build_deps_with_conan(
    conanfile: str,
    build_dir: str,
    install_dir: str,
    compiler_libcxx: str,
    compiler_version: str,
    conan_cache: Optional[str] = None,
    conan_options: Optional[List[str]] = None,
    target_os_version: Optional[str] = None,
    arch: Optional[str] = None,
    language_standards: Optional[LanguageStandardsVersion] = None,
    debug: bool = False,
    install_libs=True,
    build=None,
    announce=None,
):
    return conan_api.build_deps_with_conan(
        conanfile,
        build_dir,
        install_dir,
        compiler_libcxx,
        compiler_version,
        build if build is not None else [],
        conan_cache,
        conan_options,
        target_os_version,
        arch,
        language_standards,
        debug,
        install_libs,
        announce,
    )


def fixup_library(shared_library: str) -> None:  # pragma: no cover
    warnings.warn(
        "use uiucprescon.build.deps.fixup_library instead",
        DeprecationWarning
    )
    if sys.platform == "darwin":
        otool = shutil.which("otool")
        install_name_tool = shutil.which("install_name_tool")
        if not all([otool, install_name_tool]):
            raise FileNotFoundError(
                "Unable to fixed up because required tools are missing. "
                "Make sure that otool and install_name_tool are on "
                "the PATH."
            )
        otool = cast(str, otool)
        install_name_tool = cast(str, install_name_tool)
        dylib_regex = re.compile(
            r"^(?P<path>([@a-zA-Z./_])+)"
            r"/"
            r"(?P<file>lib[a-zA-Z/.0-9]+\.dylib)"
        )
        for line in subprocess.check_output(  # nosec B603
            [otool, "-L", shared_library], encoding="utf8"
        ).split("\n"):
            if any(
                [
                    not line.strip(),  # it's an empty line
                    str(shared_library) in line,  # it's the same library
                    "/usr/lib/" in line,  # it's a system library
                ]
            ):
                continue
            value = dylib_regex.match(line.strip())
            if value is None:
                raise ValueError(f"unable to parse {line}")
            try:
                original_path = value.group("path")
                library_name = value.group("file").strip()
            except AttributeError as e:
                raise ValueError(f"unable to parse {line}") from e
            command: List[str] = [
                install_name_tool,
                "-change",
                os.path.join(original_path, library_name),
                os.path.join("@loader_path", library_name),
                str(shared_library),
            ]
            subprocess.check_call(command)  # nosec B603


def add_conan_imports(
    import_manifest_file: str, path: str, dest: str
) -> None:  # pragma: no cover
    warnings.warn("Don't use", DeprecationWarning)
    libs: List[str] = []
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


def locate_node_deps(lib, nodes):
    for ref, node in nodes.items():
        cpp_info = node["cpp_info"]
        for comp in cpp_info.values():
            if comp["libs"] is None:
                continue
            if lib in comp["libs"]:
                return ref, node
    return None, None


def update_library_names(
    library_name: str,
    conan_build_info_fp: io.TextIOWrapper
) -> List[str]:
    return get_linking_libraries_fp(library_name, conan_build_info_fp)


def find_linking_libraries_with_conan_build_info_json(conan_build_info):
    if not os.path.exists(conan_build_info):
        raise FileNotFoundError("Missing required file conan_build_info.json.")

    with open(conan_build_info, "r", encoding="utf-8") as f:
        build_data = read_conan_build_info_json(f)
        return build_data[
            "bin_paths" if sys.platform == "win32" else "lib_paths"
        ]


def find_linking_libraries_with_conanbuildinfo_txt(conanbuildinfo):
    if not os.path.exists(conanbuildinfo):
        raise FileNotFoundError(
            f"Missing required file {conanbuildinfo}"
        )
    return parse_conan_build_info(
        conanbuildinfo,
        "bindirs" if sys.platform == "win32" else "libdirs"
    )
