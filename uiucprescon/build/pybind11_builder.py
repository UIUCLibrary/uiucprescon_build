import abc
import sys
from typing import Optional, cast, List, Set
import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext
from uiucprescon.build.utils import locate_file
from setuptools.command.build_py import build_py as BuildPy
from setuptools.extension import Extension
from setuptools.command.build_clib import build_clib as BuildClib
from distutils.ccompiler import CCompiler
import  distutils
import distutils.dep_util
import os


class AbsFindLibrary(abc.ABC):
    @abc.abstractmethod
    def locate(self, library_name: str) -> Optional[str]:
        """Abstract method for locating a library."""


class BuildPybind11Extension(build_ext):
    user_options = build_ext.user_options + [
        ('cxx-standard=', None, "C++ version to use. Default:11")
    ]

    def finalize_options(self) -> None:
        super().finalize_options()

        # self.inplace keeps getting reset by the time it is needed so
        # capture it here
        self._inplace = self.inplace

    def find_deps(
            self,
            lib: str,
            search_paths: Optional[List[str]] = None
    ) -> Optional[str]:
        search_paths = search_paths or os.environ['path'].split(";")

        search_paths.append(
            cast(
                BuildClib,
                self.get_finalized_command("build_clib")
            ).build_temp
        )

        for path in search_paths:
            if not os.path.exists(path):
                self.announce(f"Skipping invalid path: {path}", 5)
                continue
            for f in os.scandir(path):
                if f.name.lower() == lib.lower():
                    return f.path
        return None

    def find_missing_libraries(
            self,
            ext: Extension,
            strategies: Optional[List[AbsFindLibrary]] = None
    ) -> List[str]:
        strategies = strategies or [
            UseSetuptoolsCompilerFileLibrary(
                compiler=self.compiler,
                dirs=self.library_dirs + ext.library_dirs
            ),
        ]
        conanfileinfo_locations = [
            cast(
                BuildClib,
                self.get_finalized_command("build_clib")
            ).build_temp
        ]
        conan_info_dir = os.environ.get('CONAN_BUILD_INFO_DIR')
        if conan_info_dir:
            conanfileinfo_locations.insert(0, conan_info_dir)

        conanbuildinfo =\
            locate_file('conanbuildinfo.txt', conanfileinfo_locations)

        if conanbuildinfo:
            strategies.insert(
                0,
                UseConanFileBuildInfo(path=os.path.dirname(conanbuildinfo))
            )
        missing_libs = set(ext.libraries)
        for lib in ext.libraries:
            for strategy in strategies:
                if strategy.locate(lib) is not None:
                    missing_libs.remove(lib)
                    break
        return list(missing_libs)

    def build_extension(self, ext: Pybind11Extension) -> None:
        self._add_conan_libs_to_ext(ext)
        self.compiler: CCompiler
        # print(distutils._msvccompiler._find_vcvarsall)
        # og = distutils._msvccompiler._find_vc2017
        # def _find_vc2017():
        #     import pprint
        #     # print(type(os.environ))
        #     # pprint.pprint(os.environ)
        #     root = os.environ.get("PROGRAMFILES(X86)") or os.environ.get("PROGRAMFILES")
        #     # root = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
        #     print(root)
        #     results = og()
            # print(results)
            # return results
# setuptools._distutils._msvccompiler
        # setattr(distutils._msvccompiler, "_find_vc2017", _find_vc2017)
        # import subprocess
        # og = subprocess.check_output
        # def check_output(*args, **kwargs):
        #     print(*args, **kwargs)
        #     return og(*args, **kwargs)
        # setattr(subprocess, "check_output", check_output)
        # breakpoint()
        super().build_extension(ext)
        # setattr(distutils._msvccompiler)
        fullname = self.get_ext_fullname(ext.name)
        created_extension = os.path.join(
            self.build_lib,
            self.get_ext_filename(fullname)
        )
        if sys.platform == "darwin":
            self.spawn(['otool', "-L", created_extension])
        if sys.platform == "linux":
            self.spawn(['ldd', created_extension])

    def get_pybind11_include_path(self) -> str:
        return pybind11.get_include()

    def _add_conan_libs_to_ext(self, ext: Pybind11Extension) -> None:
        conan_build_info = os.path.join(
            cast(
                BuildPy,
                self.get_finalized_command("build_clib"),
            ).build_temp,
            "conanbuildinfo.txt"
        )
        if not os.path.exists(conan_build_info):
            return
        # libraries must retain order and put after existing libs
        for lib in parse_conan_build_info(conan_build_info, "libs"):
            if lib not in ext.libraries:
                ext.libraries.append(lib)

        lib_output = os.path.abspath(os.path.join(self.build_temp, "lib"))

        build_py = cast(BuildPy, self.get_finalized_command("build_py"))
        package_path = build_py.get_package_dir(build_py.packages[0])
        if os.path.exists(lib_output) and not self._inplace:
            dest = os.path.join(self.build_lib, package_path)
            self.copy_tree(lib_output, dest)

        if sys.platform == "linux":
            if not self._inplace:
                ext.runtime_library_dirs.append("$ORIGIN")
            else:
                ext.runtime_library_dirs.append(os.path.abspath(lib_output))
                ext.library_dirs.insert(0, os.path.abspath(lib_output))

        ext.library_dirs = list(
            parse_conan_build_info(conan_build_info, "libdirs")
        ) + ext.library_dirs

        ext.include_dirs = list(
            parse_conan_build_info(conan_build_info, "includedirs")
        ) + ext.include_dirs

        defines = parse_conan_build_info(conan_build_info, "defines")
        ext.define_macros = [(d, None) for d in defines] + ext.define_macros


class UseSetuptoolsCompilerFileLibrary(AbsFindLibrary):
    def __init__(self, compiler: CCompiler, dirs: List[str]) -> None:
        self.compiler = compiler
        self.dirs = dirs

    def locate(self, library_name: str) -> Optional[str]:
        return self.compiler.find_library_file(self.dirs, library_name)


class UseConanFileBuildInfo(AbsFindLibrary):

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def locate(self, library_name: str) -> Optional[str]:
        conan_build_info = os.path.join(self.path, "conanbuildinfo.txt")
        if not os.path.exists(conan_build_info):
            return None
        libs = parse_conan_build_info(conan_build_info, "libs")
        return library_name if library_name in libs else None


def parse_conan_build_info(
        conan_build_info_file: str,
        section: str
) -> Set[str]:
    items = set()
    with open(conan_build_info_file, encoding="utf-8") as f:
        found = False
        while True:
            line = f.readline()
            if not line:
                break
            if line.strip() == f"[{section}]":
                found = True
                continue
            if found:
                if line.strip() == "":
                    found = False
                    continue
                if found:
                    items.add(line.strip())
    return items
