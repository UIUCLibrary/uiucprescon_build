import re
import sys
from typing import List
from distutils.ccompiler import CCompiler
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


def get_win_deps(
        dll_name: str,
        output_file: str,
        compiler: CCompiler
) -> List[str]:
    dumpbin_exe = shutil.which('dumpbin')
    if dumpbin_exe is None:
        dumpbin_exe = 'dumpbin'
        print('Unable to locate dumpbin', file=sys.stderr)

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
