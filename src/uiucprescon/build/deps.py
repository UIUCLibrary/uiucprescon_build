"""Dependency management for libraries on different platforms."""

from __future__ import annotations

import contextlib
import functools
import os
import platform
import re
import subprocess  # nosec B404
import sys
import sysconfig
import shutil
from typing import (
    List,
    Callable,
    Optional,
    Union,
    Set,
    Dict,
    TYPE_CHECKING,
    Iterable,
    Tuple,
    Type,
)
import warnings

from setuptools.msvc import EnvironmentInfo

from .msvc import msvc14_get_vc_env

if TYPE_CHECKING:
    from distutils.ccompiler import CCompiler

__all__ = ["fixup_library"]

DEPS_REGEX = (
    r"(?<=(Image has the following dependencies:(\n){2}))((?<=\s).*\.dll\n)*"
)


def get_platform() -> str:
    if os.name == "nt":
        TARGET_TO_PLAT = {
            "x86": "win32",
            "x64": "win-amd64",
            "arm": "win-arm32",
            "arm64": "win-arm64",
        }
        target = os.environ.get("VSCMD_ARG_TGT_ARCH")
        return TARGET_TO_PLAT.get(target) or sysconfig.get_platform()
    return sysconfig.get_platform()


def parse_dumpbin_data(data: str) -> List[str]:
    dlls = []
    dep_regex = re.compile(DEPS_REGEX)
    d = dep_regex.search(data)
    if d is None:
        print(
            "Data from dumpbin does not match expected format", file=sys.stderr
        )
        print(data, file=sys.stderr)
        raise ValueError("unable to parse dumpbin file")
    for x in d.group(0).split("\n"):
        if not x.strip():
            continue
        dll = x.strip()
        dlls.append(dll)
    return dlls


def parse_dumpbin_deps(file: str) -> List[str]:  # pragma: no cover
    warnings.warn("No need to use this anymore", DeprecationWarning)
    with open(file, "r", encoding="utf-8") as f:
        return parse_dumpbin_data(f.read())


WINDOWS_SYSTEM_DLLS = {
    "ADVAPI32.dll",
    "BCRYPT.dll",
    "CRYPT32.dll",
    "GDI32.dll",
    "KERNEL32.dll",
    "MSVCP140.dll",
    "OLE32.dll",
    "SHELL32.dll",
    "USER32.dll",
    "VCRUNTIME140.dll",
    "VCRUNTIME140_1.dll",
    "WS2_32.dll",
}


def is_windows_system_lib(lib: str) -> bool:
    if os.path.exists(os.path.join("C:\\", "Windows", "System32", lib)):
        return True

    if os.path.exists(os.path.join("C:\\", "Windows", "SysWOW64", lib)):
        return True

    if lib.startswith("api-ms-win-crt"):
        return True

    if lib.startswith("python"):
        return True

    if lib.upper() in [lib.upper() for lib in WINDOWS_SYSTEM_DLLS]:
        return True

    return False


def remove_windows_system_libs(libs: List[str]) -> List[str]:
    non_system_dlls = []
    for lib in libs:
        if is_windows_system_lib(lib):
            continue
        non_system_dlls.append(lib)
    return non_system_dlls


def remove_system_dlls(dlls: List[str]) -> List[str]:  # pragma: no cover
    warnings.warn("use remove_windows_system_libs instead", DeprecationWarning)
    non_system_dlls = []
    for dll in dlls:
        if dll.startswith("api-ms-win-crt"):
            continue

        if dll.startswith("python"):
            continue

        if dll.upper() in [lib.upper() for lib in WINDOWS_SYSTEM_DLLS]:
            continue
        non_system_dlls.append(dll)
    return non_system_dlls


def locate_dumpbin_via_path2() -> Optional[str]:
    visual_studio_info = EnvironmentInfo("amd64")
    for path in visual_studio_info.return_env()["path"].split(";"):
        if not os.path.exists(path):
            continue
        dumpbin = shutil.which("dumpbin.exe", path=path)
        if dumpbin is not None:
            return dumpbin
    return None


def locate_dumpbin_via_path() -> Optional[str]:  # pragma: no cover
    warnings.warn("Use locate_dumpbin_via_path2 instead", DeprecationWarning)
    vc_env = msvc14_get_vc_env(get_platform())
    for path in vc_env.get("path", "").split(";"):
        dumpbin_exe = shutil.which("dumpbin", path=path)
        if dumpbin_exe is not None:
            return dumpbin_exe
    return None


def locate_dumpbin_using_vs_where() -> Optional[str]:
    variant = "arm64" if get_platform() == "win-arm64" else "x86.x64"
    suitable_components = (
        f"Microsoft.VisualStudio.Component.VC.Tools.{variant}",
        "Microsoft.VisualStudio.Workload.WDExpress",
    )

    for component in suitable_components:
        root = os.environ.get("ProgramFiles(x86)") or os.environ.get(
            "ProgramFiles"
        )
        if not root:
            return None
        expected_path_values = {"win-amd64": "Hostx64\\x64"}
        with contextlib.suppress(
            subprocess.CalledProcessError, OSError, UnicodeDecodeError
        ):
            dumpbin_locations = (
                subprocess.check_output(  # nosec B603
                    [
                        os.path.join(
                            root,
                            "Microsoft Visual Studio",
                            "Installer",
                            "vswhere.exe",
                        ),
                        "-latest",
                        "-prerelease",
                        "-requires",
                        component,
                        "-find",
                        "**/dumpbin.exe",
                    ]
                )
                .decode(encoding="mbcs", errors="strict")
                .strip()
                .split("\r\n")
            )
            _platform = get_platform()
            for location in dumpbin_locations:
                expected_path_value = expected_path_values.get(_platform)
                if expected_path_value is None:
                    raise ValueError(f"Unsupported platform: {_platform}")
                if expected_path_value in location:
                    return location
            return None


FIND_DUMPBIN_STRATEGIES_DEFAULT_ORDER: List[Callable[[], Optional[str]]] = [
    locate_dumpbin_via_path2,
    locate_dumpbin_using_vs_where,
]


@functools.cache
def locate_dumpbin(
    strategy: Optional[Callable[[], Optional[str]]] = None,
) -> Optional[str]:
    if strategy is not None:
        return strategy()

    for default_strategy in FIND_DUMPBIN_STRATEGIES_DEFAULT_ORDER:
        dumpbin_exe = default_strategy()
        if dumpbin_exe is not None:
            return dumpbin_exe
    return None


def get_win_deps(
    dll_name: str, output_file: str, compiler: CCompiler
) -> List[str]:  # pragma: no cover
    warnings.warn(
        "get_win_deps is deprecated, use "
        "use_dumpbin_to_determine_deps instead",
        category=DeprecationWarning,
        stacklevel=2,
    )
    if not compiler.initialized:
        compiler.initialize()

    for strategy in FIND_DUMPBIN_STRATEGIES_DEFAULT_ORDER:
        dumpbin_exe = strategy()
        if dumpbin_exe is not None:
            break
    else:
        dumpbin_exe = "dumpbin"
        print(
            "Unable to locate dumpbin. Guessing it will be on that path when "
            "it is needed",
            file=sys.stderr,
        )

    compiler.spawn(
        [
            dumpbin_exe,
            "/dependents",
            dll_name,
            f"/out:{output_file}",
        ]
    )
    deps = parse_dumpbin_deps(file=output_file)
    deps = remove_system_dlls(deps)
    return deps


def use_dumpbin_to_determine_deps(library_path: str) -> List[str]:
    visual_studio_info = EnvironmentInfo("amd64")
    dumpbin = locate_dumpbin()
    if dumpbin is None:
        raise FileNotFoundError("Unable to locate dumpbin.exe")

    dumpbin_command = [dumpbin, "/nologo", "/dependents", library_path]
    process = subprocess.run(  # nosec B603
        dumpbin_command,
        env={**os.environ.copy(), **visual_studio_info.return_env()},
        check=True,
        capture_output=True,
        encoding="mbcs",
        errors="strict",
    )
    return parse_dumpbin_data(process.stdout)


LINUX_SYSTEM_LIBRARIES = [
    "libm",
    "libstdc++",
    "libgcc",
    "libc",
    "libpthread",
    "ld-linux",
]


def use_readelf_to_determine_deps(
    library_path: str,
    run_readelf_strategy: Optional[Callable[[str], str]] = None,
) -> List[str]:
    def _run_readelf(_library_path: str) -> str:
        readelf = shutil.which("readelf")
        if readelf is None:
            raise FileNotFoundError("readelf not found")
        return subprocess.run(  # nosec B603
            [readelf, "-d", _library_path],
            check=True,
            shell=False,
            capture_output=True,
            encoding="utf8",
        ).stdout

    run_readelf: Callable[[str], str] = run_readelf_strategy or _run_readelf
    deps = []
    for line in run_readelf(library_path).split("\n"):
        if "Shared library:" in line:
            parts = line.split()
            lib = parts[-1].lstrip("[").rstrip("]")
            is_system_lib = False
            for system_lib in LINUX_SYSTEM_LIBRARIES:
                if system_lib in lib:
                    is_system_lib = True
                    continue
            if not is_system_lib:
                deps.append(lib)
    return deps


def run_patchelf_needed(
    library: str,
    patchelf_exec: str,
    command_executor: Callable[[List[str]], str],
) -> str:
    return command_executor([patchelf_exec, "--print-needed", library])


def is_linux_system_libraries(library: str) -> bool:
    if any(
        os.path.basename(library).startswith(system_lib)
        for system_lib in LINUX_SYSTEM_LIBRARIES
    ):
        return True
    return False


def use_patchelf_to_determine_deps(library: str, patchelf) -> List[str]:
    if patchelf is None:
        patchelf = shutil.which("patchelf")
    if patchelf is None:
        raise FileNotFoundError("patchelf not found")
    return [
        dep
        for dep in run_patchelf_needed(
            library,
            patchelf,
            lambda args: subprocess.run(  # nosec B603
                args, check=True, text=True, capture_output=True
            ).stdout,
        ).split()
        if not is_linux_system_libraries(dep)
    ]


def fix_up_linux_libraries(
    library: str,
    search_paths: List[str],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
) -> None:
    output_path = os.path.dirname(library)
    patchelf = shutil.which("patchelf")
    if patchelf is None:
        raise FileNotFoundError("patchelf not found")
    for dependent_library in use_patchelf_to_determine_deps(
        library, patchelf=patchelf
    ):
        if exclude_libraries and dependent_library in exclude_libraries:
            continue
        for path in search_paths:
            matching_library = os.path.join(path, dependent_library)
            if not os.path.exists(matching_library):
                continue
            copied_library = os.path.join(output_path, dependent_library)
            if not os.path.exists(copied_library):
                print(f"Copying {matching_library} to {copied_library}")
                shutil.copy2(matching_library, copied_library)
                set_rpath_command = [
                    patchelf,
                    "--set-rpath",
                    "'$ORIGIN'",
                    copied_library,
                ]
                subprocess.run(
                    set_rpath_command,  # nosec B603
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                subprocess.run(
                    [patchelf, "--shrink-rpath", copied_library],  # nosec B603
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                fix_up_linux_libraries(
                    copied_library, search_paths, exclude_libraries
                )
            break
        else:
            raise FileNotFoundError(
                f"Unable to locate {library} in search paths"
            )


def otool_subprocess(library: str, otool_exec: str) -> str:
    return subprocess.check_output(  # nosec B603
        [otool_exec, "-L", library], encoding="utf8"
    )


def iter_otool_lib_dependencies(
    library: str,
    otool_get_shared_libs_strategy: Callable[[str], str],
) -> Iterable[Tuple[str, str]]:
    regex = (
        r"^(?P<path>([@a-zA-Z./0-9-_+])+)"
        r"/"
        r"(?P<file>lib[a-zA-Z/.0-9+-]+\.dylib)"
    )
    dylib_regex = re.compile(regex)
    for line in otool_get_shared_libs_strategy(library).split("\n"):
        if any(
            [
                not line.strip(),  # it's an empty line
                str(library) in line,  # it's the same library
                "/usr/lib/" in line,  # it's a system library
                "/System/" in line,  # it's a system library
            ]
        ):
            continue
        value = dylib_regex.match(line.strip())
        if value:
            try:
                original_path = value.group("path")
                depending_library_name = value["file"].strip()
                yield original_path, depending_library_name
            except AttributeError as e:
                raise ValueError(f"unable to parse {line}") from e
        else:
            raise ValueError(f"unable to parse {line}")


def change_mac_lib_depend_shared_lib_name(
    library: str,
    original_depending_library: str,
    new_depending_library_name: str,
    install_name_tool_exec: str,
) -> None:
    command = [
        install_name_tool_exec,
        "-change",
        original_depending_library,
        os.path.join("@loader_path", new_depending_library_name),
        str(library),
    ]
    subprocess.check_call(command, shell=False)  # nosec B603


def deploy_darwin_shared_lib(
    source: str, destination: str, fixup_strategy: Callable[[str], None]
) -> None:
    shutil.copy2(source, destination)
    fixup_strategy(destination)


def fix_up_darwin_libraries(
    library: str,
    search_paths: List[str],
    get_dependencies_strat: Callable[[str], Iterable[Tuple[str, str]]],
    change_depend_shared_lib_name_strat: Callable[[str, str, str, str], None],
    deploy_library_strat: Callable[[str, str, Callable[[str], None]], None],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
) -> None:
    for original_path, depending_library_name in get_dependencies_strat(
        library
    ):
        if exclude_libraries:
            if depending_library_name.lower() in {
                lib.lower() for lib in exclude_libraries
            }:
                continue
        output_path = os.path.dirname(library)
        fixup_strategy = functools.partial(
            fix_up_darwin_libraries,
            search_paths=search_paths,
            get_dependencies_strat=get_dependencies_strat,
            deploy_library_strat=deploy_library_strat,
            change_depend_shared_lib_name_strat=(
                change_depend_shared_lib_name_strat
            ),
            exclude_libraries=exclude_libraries,
        )
        output_library = os.path.join(output_path, depending_library_name)
        if not os.path.exists(output_library):
            for path in search_paths:
                matching_library = os.path.join(path, depending_library_name)
                print(f"searching in {path}")
                if not os.path.exists(matching_library):
                    continue
                deploy_library_strat(
                    matching_library, output_library, fixup_strategy
                )
                break
            else:
                raise FileNotFoundError(
                    "unable to find matching library: "
                    f"{depending_library_name}"
                )
        change_depend_shared_lib_name_strat(
            library,
            os.path.join(original_path, depending_library_name),
            depending_library_name,
        )


class FixUpWindowsLibraries:
    def __init__(self, search_paths: List[str], exclude_libraries=None):
        super().__init__()
        self.exclude_libraries = exclude_libraries or []
        self.search_paths = search_paths
        self.dependency_search_strategy = use_dumpbin_to_determine_deps
        self.filter_system_libs = remove_windows_system_libs
        self.library_exclusion_filters = [
            lambda lib: not is_windows_system_lib(lib),
            lambda lib: lib.lower()
            not in [ex_lib.lower() for ex_lib in self.exclude_libraries],
        ]
        self.deploy = shutil.copy2

    def get_dependencies(self, library: str) -> List[str]:
        return self.dependency_search_strategy(library)

    def find_shared_library(self, library: str) -> Optional[str]:
        for path in self.search_paths:
            matching_dll = os.path.join(path, os.path.basename(library))
            if os.path.exists(matching_dll):
                return matching_dll

    def deploy_and_fixup_library(
        self, source_library: str, output_library: str
    ) -> None:
        self.deploy(source_library, output_library)
        self.fix_up(output_library)

    def fix_up(self, library: str) -> None:
        depending_libraries = self.get_dependencies(library)
        for f in self.library_exclusion_filters:
            depending_libraries = filter(f, depending_libraries)

        for depending_library in depending_libraries:
            output_library = os.path.join(
                os.path.dirname(library), depending_library
            )

            if os.path.exists(output_library):
                # No need to copy it again if already added from another dep
                continue

            if matching_dll := self.find_shared_library(
                os.path.basename(depending_library)
            ):
                print(f"Copying {matching_dll} to {output_library}")
                self.deploy_and_fixup_library(matching_dll, output_library)
            else:
                raise FileNotFoundError(
                    f"Unable to locate {depending_library}. "
                    f"Needed by {library}."
                )


def fix_up_windows_libraries(
    library: str,
    search_paths: List[str],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
    fixup_klass: Type[FixUpWindowsLibraries] = FixUpWindowsLibraries,
) -> None:
    fixer = fixup_klass(search_paths, exclude_libraries=exclude_libraries)
    return fixer.fix_up(library)


DEFAULT_FIXUP_LIBRARY_STRATEGIES: Dict[
    str, Callable[[str, List[str], Optional[Union[Set[str], List[str]]]], None]
] = {
    "Windows": fix_up_windows_libraries,
    "Darwin": lambda lib, paths, exclusions: fix_up_darwin_libraries(
        library=lib,
        search_paths=paths,
        get_dependencies_strat=functools.partial(
            iter_otool_lib_dependencies,
            otool_get_shared_libs_strategy=functools.partial(
                otool_subprocess, otool_exec=shutil.which("otool")
            ),
        ),
        change_depend_shared_lib_name_strat=functools.partial(
            change_mac_lib_depend_shared_lib_name,
            install_name_tool_exec=shutil.which("install_name_tool"),
        ),
        exclude_libraries=exclusions,
        deploy_library_strat=functools.partial(deploy_darwin_shared_lib),
    ),
    "Linux": fix_up_linux_libraries,
}


def fixup_library(
    library: str,
    search_paths: List[str],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
):
    """Fix up the library by add its dependencies adjacent to it."""
    fix_up_strategy = DEFAULT_FIXUP_LIBRARY_STRATEGIES.get(platform.system())
    if fix_up_strategy is None:
        raise NotImplementedError(
            f"Fixup strategy for {platform.system()} is not implemented"
        )
    fix_up_strategy(library, search_paths, exclude_libraries)
