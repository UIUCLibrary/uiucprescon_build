import json
import os
import shutil
import sys

import pytest
from uiucprescon import build
from importlib_metadata import version


@pytest.fixture()
def pybind_only_example(tmp_path):
    source_root = tmp_path / "package"
    source_root.mkdir()
    pybind_only_source_folder = os.path.join(
        os.path.dirname(__file__), "test_files", "pybind_only"
    )
    shutil.copytree(pybind_only_source_folder, source_root, dirs_exist_ok=True)
    return source_root


def test_conan_integration(tmp_path, pybind_only_example, monkeypatch):
    home = tmp_path / "home"
    output = tmp_path / "output"
    monkeypatch.chdir(pybind_only_example)
    monkeypatch.setenv("HOME", str(home))
    build.build_wheel(str(output))
    assert any(f.startswith("dummy") for f in os.listdir(output))


@pytest.fixture
def zstd_from_conan_example(tmp_path):
    source_root = tmp_path / "package"
    source_root.mkdir()
    pybind_only_source_folder = os.path.join(
        os.path.dirname(__file__), "test_files", "zstd_from_conan"
    )
    shutil.copytree(pybind_only_source_folder, source_root, dirs_exist_ok=True)
    return source_root


@pytest.mark.skipif(
    sys.version_info < (3, 10) and sys.platform == "win32",
    reason="There is an issue with module_from_spec on windows and Python 3.9",
)
@pytest.mark.skipif(
    version("conan") < "2.0.0", reason="Requires Conan 2.0 or higher"
)
def test_conan_integration_with_shared_library(
    tmp_path,
    monkeypatch,
    zstd_from_conan_example,
):
    home = tmp_path / "home"
    output = tmp_path / "output"
    monkeypatch.chdir(zstd_from_conan_example)
    monkeypatch.setenv("HOME", str(home))
    build.build_wheel(str(output))
    assert any(f.startswith("dummy") for f in os.listdir(output))
