import os
import sys
from typing import cast
import tokenize
import json
from setuptools import Command
from setuptools import build_meta
from setuptools.command.build_ext import build_ext


class BuildExtInfo(Command):
    """
    A command to build the extension and return build information.
    This is a placeholder for the actual implementation.
    """

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
            self.build_dir = os.path.join(
                build_ext_cmd.build_temp, "setuptools_introspection"
            )

    def run(self) -> None:
        """Run the command to build the extension."""
        print("inspecting setup.py...")
        if not os.path.exists(self.build_dir):
            self.mkpath(self.build_dir)

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
            os.path.join(self.build_dir, "setuptools_introspection.json"), "w"
        ) as f:
            json_string = json.dumps(
                data, indent=4
            )  # indent for pretty printing
            f.write(json_string)


def get_extension_build_info():
    og = sys.argv
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

    finally:
        sys.argv = og
    with open(setuptools_introspection, "r") as f:
        return json.load(f)
