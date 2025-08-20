from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension
from uiucprescon.build.pybind11_builder import BuildPybind11Extension

setup(
    name="dummy",
    ext_modules=[
        Pybind11Extension(
            "dummy.spam",
            sources=[
                "spamextension.cpp",
            ],
            language="c++",
        )
    ],
    cmdclass={"build_ext": BuildPybind11Extension},
)
