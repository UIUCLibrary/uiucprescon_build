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
        "libs": ['eggs'],
        "metadata": {'eggs': {"libs": []}}
    }
    conan_libs.update_extension2(extension, text_metadata)
    assert "eggs" in extension.libraries

def test_get_conan_options(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()

    pyproject = source_root / "pyproject.toml"
    pyproject.write_text(f"""
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


# def test_build_deps_with_conan_calls_install(tmp_path, monkeypatch):
#     build_dir = tmp_path / "build"
#     install_dir = tmp_path / "install"
#     conan_cache = tmp_path / "conan_cache"
#     build_dir.mkdir()
#     conan_object = Mock()
#     monkeypatch.setattr(conan_libs.conan_api, "Conan", Mock(return_value=conan_object))
#     conan_libs.build_deps_with_conan(
#         build_dir,
#         install_dir,
#         "libstdc",
#         "14.3",
#         conan_cache=conan_cache
#     )
#     assert conan_object.install.called
