"""This module provides functionality to introspect of setup.py extensions."""

import os
import sys
from typing import cast, Optional
import tokenize
import json
from setuptools import Command
from setuptools import build_meta
from setuptools.command.build_ext import build_ext


class BuildExtInfo(Command):
    """A command to build the extension and return build information."""

    build_dir: Optional[str]

    description = "Build the extension and return build information."

    def initialize_options(self) -> None:
        """Initialize options for the command."""
        self.build_dir = None

    def finalize_options(self) -> None:
        """Finalize options for the command."""
        if self.build_dir is None:
            build_ext_cmd = cast(
                build_ext, self.get_finalized_command("build_ext")
            )
            if build_ext_cmd.build_temp is None:
                self.warn(
                    "build_ext.build_temp was not set and will "
                    "affect BuildExtInfo"
                )
                self.build_dir = "build"
            else:
                build_ext_build_dir: str = build_ext_cmd.build_temp
                self.build_dir = os.path.join(
                    build_ext_build_dir, "setuptools_introspection"
                )

    def run(self) -> None:
        """Run the command to build the extension."""
        print("inspecting setup.py...")
        if self.build_dir is None:
            self.warn("build_dir was not set")
            return
        build_dir: str = self.build_dir
        if not os.path.exists(build_dir):
            self.mkpath(build_dir)

        build_ext_cmd = cast(
            build_ext, self.get_finalized_command("build_ext")
        )
        data = {"extensions": []}
        for e in build_ext_cmd.extensions:
            data["extensions"].append(
                {
                    "name": e.name,
                    "define_macros": e.define_macros,
                    "include_dirs": e.include_dirs,
                    "libraries": e.libraries,
                    "cxx_std": getattr(e, "cxx_std", None),
                }
            )
        with open(
            os.path.join(build_dir, "setuptools_introspection.json"),
            "w",
            encoding="utf-8"
        ) as f:
            json_string = json.dumps(
                data, indent=4
            )  # indent for pretty printing
            f.write(json_string)


def get_extension_build_info():
    """Retrieve the build information for extensions from the setup.py file.

    This creates a setuptools_introspection.json file in the build directory
    """
    og = sys.argv.copy()
    setuptools_introspection = None
    try:
        sys.argv = [
            *sys.argv[:1],
            "build_ext_info",
        ]
        with build_meta.Distribution.patch():
            build_meta.Distribution.patch()
            setup = os.path.abspath("setup.py")
            if not os.path.exists(setup):
                return {"extensions": []}
            code = tokenize.open(setup).read().replace("\r\n", "\n")
            exec(code, {**locals(), **{"__file__": setup}})  # nosec B102
            for root, dirs, files in os.walk("build"):
                if len(os.path.split(root)) > 10:
                    raise FileNotFoundError(
                        "Too many nested directories, skipping introspection."
                    )
                for file in files:
                    if file == "setuptools_introspection.json":
                        setuptools_introspection = os.path.join(root, file)
                        break
                if setuptools_introspection:
                    break
            else:
                raise FileNotFoundError(
                    "unable to find setuptools_introspection.json file. "
                )

        with open(setuptools_introspection, "r", encoding="utf-8") as f:
            return json.load(f)
    finally:
        sys.argv = og
