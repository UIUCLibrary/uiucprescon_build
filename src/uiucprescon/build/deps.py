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
from setuptools.msvc import EnvironmentInfo
from typing import (
    List, Callable, Optional, Union, Set, Dict, cast, TYPE_CHECKING
)
import warnings

from .msvc import msvc14_get_vc_env

if TYPE_CHECKING:
    from distutils.ccompiler import CCompiler

DEPS_REGEX = (
    r"(?<=(Image has the following dependencies:(\n){2}))((?<=\s).*\.dll\n)*"
)


def get_platform() -> str:
    if os.name == 'nt':
        TARGET_TO_PLAT = {
            'x86': 'win32',
            'x64': 'win-amd64',
            'arm': 'win-arm32',
            'arm64': 'win-arm64',
        }
        target = os.environ.get('VSCMD_ARG_TGT_ARCH')
        return TARGET_TO_PLAT.get(target) or sysconfig.get_platform()
    return sysconfig.get_platform()


def parse_dumpbin_data(data: str) -> List[str]:
    dlls = []
    dep_regex = re.compile(DEPS_REGEX)
    print(f"Using {DEPS_REGEX}")
    d = dep_regex.search(data)
    if d is None:
        print(
            "Data from dumpbin does not match expected format", file=sys.stderr
        )
        print(data, file=sys.stderr)
        raise ValueError("unable to parse dumpbin file")
    for x in d.group(0).split("\n"):
        if x.strip() == "":
            continue
        dll = x.strip()
        dlls.append(dll)
    return dlls


def parse_dumpbin_deps(file: str) -> List[str]:
    with open(file) as f:
        return parse_dumpbin_data(f.read())


WINDOWS_SYSTEM_DLLS = [
    "ADVAPI32.dll",
    "CRYPT32.dll",
    "KERNEL32.dll",
    "USER32.dll",
    "WS2_32.dll",
    "GDI32.dll",
]


def remove_system_dlls(dlls: List[str]) -> List[str]:
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


def locate_dumpbin_via_path() -> Optional[str]:
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
    strategy: Optional[Callable[[], Optional[str]]] = None
) -> Optional[str]:
    if strategy is not None:
        return strategy()

    for strategy in FIND_DUMPBIN_STRATEGIES_DEFAULT_ORDER:
        dumpbin_exe = strategy()
        if dumpbin_exe is not None:
            return dumpbin_exe
    return None


def get_win_deps(
    dll_name: str, output_file: str, compiler: CCompiler
) -> List[str]:
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
        [dumpbin_exe, "/dependents", dll_name, f"/out:{output_file}"]
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
    system_libs = [
        "libm", "libstdc++", "libgcc", "libc", "libpthread", "ld-linux"
    ]
    for line in run_readelf(library_path).split("\n"):
        if "Shared library:" in line:
            parts = line.split()
            lib = parts[-1].lstrip("[").rstrip("]")
            is_system_lib = False
            for system_lib in system_libs:
                if system_lib in lib:
                    is_system_lib = True
                    continue
            if not is_system_lib:
                deps.append(lib)
    return deps


def use_patchelf_to_determine_deps(library, patchelf):
    if patchelf is None:
        patchelf = shutil.which("patchelf")
    if patchelf is None:
        raise FileNotFoundError("patchelf not found")
    system_libs = [
        "libm", "libstdc++", "libgcc", "libc", "libpthread", "ld-linux"
    ]
    deps = []
    for dep in subprocess.run(
            [patchelf, "--print-needed", library],
            check=True,
            text=True,
            capture_output=True
    ).stdout.split():
        if any(dep.startswith(lib) for lib in system_libs):
            continue
        deps.append(dep)
    return deps


def fix_up_linux_libraries(
    library: str,
    search_paths: List[str],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
) -> None:
    output_path = os.path.dirname(library)
    patchelf = shutil.which("patchelf")
    if patchelf is None:
        raise FileNotFoundError("patchelf not found")
    for library in use_patchelf_to_determine_deps(library, patchelf=patchelf):
        if exclude_libraries and library in exclude_libraries:
            continue
        for path in search_paths:
            matching_library = os.path.join(path, library)
            if not os.path.exists(matching_library):
                continue
            copied_library = os.path.join(output_path, library)
            if not os.path.exists(copied_library):
                print(f"Copying {matching_library} to {copied_library}")
                shutil.copy2(matching_library, output_path)

                subprocess.run(
                    [
                        patchelf,
                        "--set-rpath",
                        "'$ORIGIN'",
                        copied_library
                    ],  # nosec B603
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                subprocess.run(
                    [
                        patchelf,
                        "--shrink-rpath",
                        copied_library
                    ],  # nosec B603
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                fix_up_linux_libraries(
                    copied_library, search_paths, exclude_libraries
                )
            break
        else:
            raise FileNotFoundError(
                f"Unable to locate {library} in search paths"
            )


def fix_up_darwin_libraries(
    library: str,
    search_paths: List[str],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
) -> None:
    otool = shutil.which("otool")
    install_name_tool = shutil.which("install_name_tool")
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
        r"^(?P<path>([@a-zA-Z./_])+)"
        r"/"
        r"(?P<file>lib[a-zA-Z/.0-9]+\.dylib)"
    )
    for line in subprocess.check_output(  # nosec B603
        [otool, "-L", library], encoding="utf8"
    ).split("\n"):
        if any(
            [
                line.strip() == "",  # it's an empty line
                str(library) in line,  # it's the same library
                "/usr/lib/" in line,  # it's a system library
                "/System/Library/Frameworks/" in line,  # it's a system library
            ]
        ):
            continue
        value = dylib_regex.match(line.strip())
        if value:
            try:
                original_path = value.group("path")
                depending_library_name = value["file"].strip()
            except AttributeError as e:
                raise ValueError(f"unable to parse {line}") from e
        else:
            raise ValueError(f"unable to parse {line}")
        if exclude_libraries:
            if depending_library_name.lower() in {
                lib.lower() for lib in exclude_libraries
            }:
                continue
        output_path = os.path.dirname(library)
        if not os.path.exists(
            os.path.join(output_path, depending_library_name)
        ):
            for path in search_paths:
                matching_library = os.path.join(path, depending_library_name)
                print(f"searching in {path}")
                if not os.path.exists(matching_library):
                    continue
                shutil.copy2(matching_library, output_path)
                fix_up_darwin_libraries(
                    os.path.join(output_path, depending_library_name),
                    search_paths,
                    exclude_libraries,
                )
                break
            else:
                raise FileNotFoundError(
                    "unable to find matching library: "
                    f"{depending_library_name}"
                )

        command = [
            install_name_tool,
            "-change",
            os.path.join(original_path, depending_library_name),
            os.path.join("@loader_path", depending_library_name),
            str(library),
        ]
        subprocess.check_call(command, shell=False)  # nosec B603


def fix_up_windows_libraries(
    library: str,
    search_paths: List[str],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
    determine_dependencies_strategy: Callable[
        [str], List[str]
    ] = use_dumpbin_to_determine_deps,
) -> None:
    depending_libraries = remove_system_dlls(
        determine_dependencies_strategy(library)
    )
    output_path = os.path.dirname(library)
    for depending_library in depending_libraries:
        if exclude_libraries:
            if depending_library.lower() in {
                lib.lower() for lib in exclude_libraries
            }:
                continue
        if not os.path.exists(os.path.join(output_path, depending_library)):
            for path in search_paths:
                matching_dll = os.path.join(
                    path, os.path.basename(depending_library)
                )
                if os.path.exists(matching_dll):
                    output_library = os.path.join(
                        output_path, depending_library
                    )
                    print(f"Copying {matching_dll} to {output_library}")
                    shutil.copy2(matching_dll, output_library)
                    fixup_library(
                        output_library, search_paths, exclude_libraries
                    )
                    break
            else:
                raise FileNotFoundError(
                    f"Unable to locate {depending_library}"
                )


DEFAULT_FIXUP_LIBRARY_STRATEGIES: Dict[
    str, Callable[[str, List[str], Optional[Union[Set[str], List[str]]]], None]
] = {
    "Windows": fix_up_windows_libraries,
    "Darwin": fix_up_darwin_libraries,
    "Linux": fix_up_linux_libraries,
}


def fixup_library(
    library: str,
    search_paths: List[str],
    exclude_libraries: Optional[Union[Set[str], List[str]]] = None,
):
    fix_up_strategy = DEFAULT_FIXUP_LIBRARY_STRATEGIES.get(platform.system())
    if fix_up_strategy is None:
        raise NotImplementedError(
            f"Fixup strategy for {platform.system()} is not implemented"
        )
    fix_up_strategy(library, search_paths, exclude_libraries)
