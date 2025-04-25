import os
import re
import subprocess
import sys
import shutil
import abc
import typing
from typing import Dict, List, Optional, cast, Set, Tuple, Union
import setuptools
import distutils.ccompiler
from pathlib import Path
from uiucprescon.build.deps import get_win_deps
from uiucprescon.build.compiler_info import (
    get_compiler_version,
)
import json
from setuptools.dist import Distribution
from setuptools.command.build_ext import build_ext as BuildExt
from setuptools.command.build_py import build_py as BuildPy
from setuptools.command.build_clib import build_clib as BuildClib
import toml
from uiucprescon.build.conan import conan_api
from uiucprescon.build.conan.files import ConanBuildInfo, ConanBuildInfoParser

__all__ = ["ConanBuildInfoParser"]


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
            assert os.path.exists(path)
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
        with open(self.filename) as f:
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
    ]

    description = "Get the required dependencies from a Conan package manager"

    def initialize_options(self) -> None:
        self.conan_cache: Optional[str] = None
        self.compiler_version: Optional[str] = None
        self.compiler_libcxx: Optional[str] = None
        self.conanfile: Optional[str] = None

    def __init__(self, dist: setuptools.dist.Distribution, **kw: str) -> None:
        self.install_libs = True
        self.build_libs = ["outdated"]
        super().__init__(dist, **kw)

    def finalize_options(self) -> None:
        if self.conan_cache is None:
            build_ext_cmd = cast(
                BuildExt, self.get_finalized_command("build_ext")
            )
            build_dir = build_ext_cmd.build_temp

            self.conan_cache = os.path.join(
                os.environ.get("CONAN_USER_HOME", build_dir), ".conan"
            )
        if self.compiler_libcxx is None:
            self.compiler_libcxx = os.getenv("CONAN_COMPILER_LIBCXX")
        if self.compiler_version is None:
            self.compiler_version = os.getenv(
                "CONAN_COMPILER_VERSION", get_compiler_version()
            )

    def getConanBuildInfo(self, root_dir: str) -> Optional[str]:
        for root, dirs, files in os.walk(root_dir):
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
        build_clib = cast(BuildClib, self.get_finalized_command("build_clib"))

        build_ext = cast(BuildExt, self.get_finalized_command("build_ext"))
        if self.install_libs:
            if build_ext._inplace:
                install_dir = os.path.abspath(build_ext.build_temp)
            else:
                build_py = cast(
                    BuildPy, self.get_finalized_command("build_py")
                )
                # FIXME: This breaks if the source folder from the package is located in a src directory
                install_dir = os.path.abspath(
                    os.path.join(
                        build_py.build_lib,
                        build_py.get_package_dir(build_py.packages[0]),
                    )
                )
        else:
            install_dir = build_ext.build_temp
        build_dir = os.path.join(build_clib.build_temp, "conan")
        conan_cache = self.conan_cache
        if conan_cache and not os.path.exists(conan_cache):
            self.mkpath(conan_cache)
            self.announce(f"Created {conan_cache} for conan cache", 5)
        if not os.path.exists(build_dir):
            self.mkpath(build_dir)
        self.announce(f"Using {conan_cache} for conan cache", 5)
        metadata = build_deps_with_conan(
            conanfile=self.conanfile,
            build_dir=build_dir,
            install_dir=os.path.abspath(install_dir),
            compiler_libcxx=self.compiler_libcxx,
            compiler_version=self.compiler_version,
            conan_options=get_conan_options(),
            conan_cache=conan_cache,
            install_libs=self.install_libs,
            announce=self.announce,
        )
        build_ext_cmd = cast(BuildExt, self.get_finalized_command("build_ext"))
        for extension in build_ext_cmd.extensions:
            if build_ext._inplace:
                extension.runtime_library_dirs.append(
                    os.path.abspath(install_dir)
                )
            update_extension2(extension, metadata)
            extension.library_dirs.insert(0, install_dir)
            if sys.platform == "darwin":
                extension.runtime_library_dirs.append("@loader_path")
            elif sys.platform == "linux":
                if "$ORIGIN" not in extension.runtime_library_dirs:
                    extension.runtime_library_dirs.append("$ORIGIN")


def _get_source_root(dist: Distribution) -> str:
    project_files = ["pyproject.toml", "setup.py"]
    path = dist.src_root or os.curdir
    for project_file in project_files:
        project_file_path = Path(path, project_file)
        if os.path.exists(project_file_path):
            return os.path.abspath(path)
    return os.path.abspath(path)


def _find_conanfile(path: str) -> Optional[str]:
    conanfile_types = ["conanfile.py"]
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
        command.compiler_libcxx = config_settings.get("conan_compiler_libcxx")
        command.compiler_version = config_settings.get(
            "conan_compiler_version", get_compiler_version()
        )
    if conan_cache is None:
        conan_home = os.getenv("CONAN_USER_HOME")
        if conan_home is not None:
            conan_cache = os.path.join(conan_home, ".conan")

    if conan_cache is None:
        conan_cache = os.path.join(
            cast(
                BuildExt, command.get_finalized_command("build_ext")
            ).build_temp,
            ".conan",
        )

    command.finalize_options()
    command.conan_cache = conan_cache
    command.run()


def get_pyproject_toml_data() -> Dict[str, typing.Any]:
    pyproj_toml = Path("pyproject.toml")
    with open(pyproj_toml) as f:
        return toml.load(f)


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
    announce=None,
):
    return conan_api.build_deps_with_conan(
        conanfile,
        build_dir,
        install_dir,
        compiler_libcxx,
        compiler_version,
        conan_cache,
        conan_options,
        debug,
        install_libs,
        build,
        announce,
    )


def fixup_library(shared_library: str) -> None:
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
        for line in subprocess.check_output(
            [otool, "-L", shared_library], encoding="utf8"
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
            subprocess.check_call(command)


def add_conan_imports(import_manifest_file: str, path: str, dest: str) -> None:
    libs: List[str] = []
    with open(import_manifest_file, "r", encoding="utf8") as f:
        for line in f.readlines():
            if ":" not in line:
                continue

            try:
                file_name, hash_value = line.strip().split(": ")
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
