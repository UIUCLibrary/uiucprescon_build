import contextlib
import os
import re
import subprocess
import sys
from distutils.util import get_platform
from typing import List, Callable, Optional
from distutils.ccompiler import CCompiler
from .msvc import msvc14_get_vc_env
import shutil
DEPS_REGEX = \
    r'(?<=(Image has the following dependencies:(\n){2}))((?<=\s).*\.dll\n)*'


def parse_dumpbin_deps(file: str) -> List[str]:

    dlls = []
    dep_regex = re.compile(DEPS_REGEX)

    with open(file) as f:
        d = dep_regex.search(f.read())
        if d is None:
            raise ValueError('unable to parse dumpbin file')
        for x in d.group(0).split("\n"):
            if x.strip() == "":
                continue
            dll = x.strip()
            dlls.append(dll)
    return dlls


def remove_system_dlls(dlls: List[str]) -> List[str]:
    non_system_dlls = []
    for dll in dlls:
        if dll.startswith("api-ms-win-crt"):
            continue

        if dll.startswith("python"):
            continue

        if dll == "KERNEL32.dll":
            continue
        non_system_dlls.append(dll)
    return non_system_dlls


def locate_dumpbin_via_path() -> Optional[str]:
    vc_env = msvc14_get_vc_env(get_platform())
    for path in vc_env.get('path', '').split(";"):
        dumpbin_exe = shutil.which('dumpbin', path=path)
        if dumpbin_exe is not None:
            return dumpbin_exe
    return None


def locate_dumpbin_using_vs_where() -> Optional[str]:
    variant = 'arm64' if get_platform() == 'win-arm64' else 'x86.x64'
    suitable_components = (
        f"Microsoft.VisualStudio.Component.VC.Tools.{variant}",
        "Microsoft.VisualStudio.Workload.WDExpress",
    )

    for component in suitable_components:
        root = (
            os.environ.get("ProgramFiles(x86)") or
            os.environ.get("ProgramFiles")
        )
        if not root:
            return None
        expected_path_values = {
            'win-amd64': "Hostx64\\x64"
        }
        with contextlib.suppress(
                subprocess.CalledProcessError, OSError, UnicodeDecodeError
        ):
            dumpbin_locations = (
                subprocess.check_output([
                    os.path.join(
                        root, "Microsoft Visual Studio",
                        "Installer", "vswhere.exe"
                    ),
                    "-latest",
                    "-prerelease",
                    "-requires",
                    component,
                    "-find",
                    "**/dumpbin.exe",
                ])
                .decode(encoding="mbcs", errors="strict")
                .strip().split("\r\n")
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
    locate_dumpbin_via_path,
    locate_dumpbin_using_vs_where
]


def get_win_deps(
        dll_name: str,
        output_file: str,
        compiler: CCompiler
) -> List[str]:

    if not compiler.initialized:
        compiler.initialize()

    for strategy in FIND_DUMPBIN_STRATEGIES_DEFAULT_ORDER:
        dumpbin_exe = strategy()
        if dumpbin_exe is not None:
            break
    else:
        dumpbin_exe = 'dumpbin'
        print(
            'Unable to locate dumpbin. Guessing it will be on that path when '
            'it is needed',
            file=sys.stderr
        )

    compiler.spawn(
        [
            dumpbin_exe,
            '/dependents',
            dll_name,
            f'/out:{output_file}'
        ]
    )
    deps = parse_dumpbin_deps(file=output_file)
    deps = remove_system_dlls(deps)
    return deps
