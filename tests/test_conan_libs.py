from uiucprescon.build import conan_libs
from setuptools import Extension
import sys


def test_update_extension2():
    extension = Extension(
        name="spam",
        sources=[],
        libraries=[
            "eggs"
        ]
    )
    text_metadata = {
        "include_paths": [],
        "lib_paths": [],
        "libs": ["eggs"],
        "metadata": {"eggs": {"libs": []}}
    }
    conan_libs.update_extension2(extension, text_metadata)
    assert "eggs" in extension.libraries


def test_get_conan_options(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()

    pyproject = source_root / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "dummy"
    """)
    monkeypatch.chdir(source_root)
    conan_libs.get_conan_options()


def test_get_conan_options_localbuilder(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()

    pyproject = source_root / "pyproject.toml"
    pyproject.write_text(f"""
[project]
name = "dummy"
[localbuilder.{sys.platform}]
conan_options=[]

    """)
    monkeypatch.chdir(source_root)
    conan_libs.get_conan_options()
