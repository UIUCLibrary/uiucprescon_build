import json
import os

import pytest

from uiucprescon import build
from importlib_metadata import version

def test_conan_integration(tmp_path, monkeypatch):
    source_root = tmp_path / "package"
    source_root.mkdir()

    home = tmp_path / "home"

    setup_py = source_root / "setup.py"
    setup_py.write_text("""
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension
from uiucprescon.build.pybind11_builder import BuildPybind11Extension

setup(
    name='dummy',
    ext_modules=[
        Pybind11Extension(
            "dummy.spam",
            sources=[
                "spamextension.cpp",
            ],
            language="c++",
        )
    ],
    cmdclass={
        "build_ext": BuildPybind11Extension
    },
    )    
    """)

    pyproject = source_root / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "dummy"
version = "1.0"
    """)

    conanfile = source_root / "conanfile.py"
    conanfile.write_text("""
from conan import ConanFile
class Dummy(ConanFile):
    requires = []
    """)

    myextension_cpp = source_root / "spamextension.cpp"
    myextension_cpp.write_text("""#include <iostream>
    #include <pybind11/pybind11.h>
    PYBIND11_MODULE(spam, m){
        m.doc() = R"pbdoc(Spam lovely spam)pbdoc";
    }
    """)

    output = tmp_path / "output"
    with open(pyproject, "r", encoding="utf-8") as f:
        print(f.read())
    monkeypatch.chdir(source_root)
    monkeypatch.setenv("HOME", str(home))
    build.build_wheel(str(output))
    assert any(f.startswith("dummy") for f in os.listdir(output))

@pytest.fixture(scope="session")
def zstd_example_config():
    config_json = os.path.join(os.path.dirname(__file__), 'conan_test_libraries.json')
    with open(config_json, "r", encoding="utf-8") as f:
        return json.load(f)['conan_test_libraries']["2"]["zstd"]

@pytest.mark.skipif(version("conan") < "2.0.0", reason="Requires Conan 2.0 or higher")
def test_conan_integration_with_shared_library(tmp_path, monkeypatch, zstd_example_config):
    source_root = tmp_path / "package"
    source_root.mkdir()

    home = tmp_path / "home"

    setup_py = source_root / "setup.py"
    setup_py.write_text("""
from setuptools import setup
import os
from pybind11.setup_helpers import Pybind11Extension
from uiucprescon.build.pybind11_builder import BuildPybind11Extension
import importlib.util
class BuildPybind11Extensions(BuildPybind11Extension):
    def run(self):
        conan_cmd = self.get_finalized_command("build_conan")
        conan_cmd.run()
        # breakpoint()
        super().run()
        module_path = os.path.join(self.build_lib, 'dummy', self.get_ext_filename("spam"))
        module_name = 'dummy.spam' # The name you want to assign to the imported module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        my_dynamic_module = importlib.util.module_from_spec(spec)
        zstd_version = my_dynamic_module.get_version()
        assert zstd_version == "1.5.7", f"zstd_version version mismatch, expected: 1.5.7 got: {zstd_version}"

setup(
    name='dummy',
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
    cmdclass={
        "build_ext": BuildPybind11Extensions
    },
    )    
    """)

    pyproject = source_root / "pyproject.toml"
    requires = ",\n".join([f'       "{r}"' for r in zstd_example_config["requires"]])
    default_options_string = str(
        ",\n".join([f'       "{k}": {v}' for k, v in zstd_example_config['default_options'].items()])
    )
    pyproject.write_text("""
[project]
name = "dummy"
version = "1.0"
    """)

    conanfile = source_root / "conanfile.py"
    conanfile.write_text(f"""
from conan import ConanFile
class Dummy(ConanFile):
    requires = [
{requires}
    ]
    default_options = {{
{default_options_string}
    }}
""")

    myextension_cpp = source_root / "spamextension.cpp"
    myextension_cpp.write_text("""#include <iostream>
    #include "zstd.h"
    #include <pybind11/pybind11.h>
    const std::string get_version(){
        return ZSTD_versionString();
    }
    PYBIND11_MODULE(spam, m){
        m.doc() = R"pbdoc(Spam lovely spam)pbdoc";
        m.def("get_version", &get_version, "Get the version of library linked to");
    }
    """)

    output = tmp_path / "output"
    monkeypatch.chdir(source_root)
    monkeypatch.setenv("HOME", str(home))
    build.build_wheel(str(output))
    assert any(f.startswith("dummy") for f in os.listdir(output))

