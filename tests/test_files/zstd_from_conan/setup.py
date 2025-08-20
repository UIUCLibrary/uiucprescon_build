from setuptools import setup
import os
from pybind11.setup_helpers import Pybind11Extension
from uiucprescon.build.pybind11_builder import BuildPybind11Extension
import importlib.util


class BuildPybind11Extensions(BuildPybind11Extension):
    def run(self):
        conan_cmd = self.get_finalized_command("build_conan")
        conan_cmd.run()
        super().run()
        module_path = os.path.join(
            self.build_lib, "dummy", self.get_ext_filename("spam")
        )
        module_name = "dummy.spam"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        my_dynamic_module = importlib.util.module_from_spec(spec)
        zstd_ver = my_dynamic_module.get_version()
        assert zstd_ver == "1.5.7", (
            f"version mismatch, expected: 1.5.7 got: {zstd_ver}"
        )


setup(
    name="dummy",
    ext_modules=[
        Pybind11Extension(
            "dummy.spam",
            sources=[
                "spamextension.cpp",
            ],
            language="c++",
            libraries=["zstd"],
        )
    ],
    cmdclass={"build_ext": BuildPybind11Extensions},
)
