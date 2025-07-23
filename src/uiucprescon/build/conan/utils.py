"""Utility functions for working with Conan."""

import dataclasses
import os
import re
import shutil
import subprocess  # nosec B404
import sys
import warnings
from importlib.metadata import version
from pathlib import Path
from typing import Tuple, cast, List, Optional


@dataclasses.dataclass
class LanguageStandardsVersion:
    """Data class to hold the C and C++ standards versions."""

    cpp_std: Optional[str] = None
    c_std: Optional[str] = None


def get_conan_version() -> Tuple[str, str]:  # pragma: no cover
    """Don't use this function, it's deprecated & will be removed."""
    warnings.warn("use `version('conan')` instead", DeprecationWarning)
    return tuple(b for b in version("conan").split("."))


def fixup_library(shared_library: str) -> None:  # pragma: no cover
    """Don't use this function, it's deprecated & will be removed."""
    warnings.warn(
        "use `uiucprescon.build.deps.fixup_library` instead",
        DeprecationWarning
    )  # pragma: no cover
    if sys.platform == "darwin":
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
        for line in subprocess.check_output(
            [otool, "-L", shared_library],
                encoding="utf8",
                shell=False  # nosec B603
        ).split("\n"):
            if any(
                [
                    line.strip() == "",  # it's an empty line
                    str(shared_library) in line,  # it's the same library
                    "/usr/lib/" in line,  # it's a system library
                    "/System/Library/Frameworks/"
                    in line,  # it's a system library
                ]
            ):
                continue
            value = dylib_regex.match(line.strip())
            if value:
                try:
                    original_path = value.group("path")
                    library_name = value["file"].strip()
                except AttributeError as e:
                    raise ValueError(f"unable to parse {line}") from e
            else:
                raise ValueError(f"unable to parse {line}")

            command = [
                install_name_tool,
                "-change",
                os.path.join(original_path, library_name),
                os.path.join("@loader_path", library_name),
                str(shared_library),
            ]
            subprocess.check_call(command)  # nosec B603


def copy_conan_imports_from_manifest(
    import_manifest_file: str, path: str, dest: str
) -> None:
    """Copy libraries from a Conan import manifest file to destination path."""
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
