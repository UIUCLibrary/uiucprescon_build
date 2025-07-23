# ruff: noqa: E501
import os.path
from unittest.mock import Mock, ANY

import pytest

from uiucprescon.build import deps


@pytest.mark.parametrize(
    "given, expected",
    [
        (
                ["openjpg.dll", "KERNEL32.dll"],
                ["openjpg.dll"]
        ),
        (
                ["openjpg.dll", "kernel32.dll"],
                ["openjpg.dll"]
        ),
        (
                ["openjpg.dll", "python.dll"],
                ["openjpg.dll"]
        ),
        (
                ["openjpg.dll", "api-ms-win-crt-runtime-l1-1-0.dll"],
                ["openjpg.dll"]
        ),
    ]
)
def test_remove_windows_system_libs(given, expected):
    assert deps.remove_windows_system_libs(given) == expected


def test_use_readelf_to_determine_deps():
    def dummy_readelf(library):
        return """
Dynamic section at offset 0x3ae000 contains 31 entries:
Tag        Type                         Name/Value
0x0000000000000001 (NEEDED)             Shared library: [bar.so]
0x0000000000000001 (NEEDED)             Shared library: [libstdc++.so.6]
0x0000000000000001 (NEEDED)             Shared library: [libm.so.6]
0x0000000000000001 (NEEDED)             Shared library: [libgcc_s.so.1]
0x0000000000000001 (NEEDED)             Shared library: [libpthread.so.0]
0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN]
0x000000000000000c (INIT)               0x4d000
0x000000000000000d (FINI)               0x2e3200
0x0000000000000019 (INIT_ARRAY)         0x3ab980
0x000000000000001b (INIT_ARRAYSZ)       248 (bytes)
0x000000000000001a (FINI_ARRAY)         0x3aba78
0x000000000000001c (FINI_ARRAYSZ)       8 (bytes)
0x000000006ffffef5 (GNU_HASH)           0x260
0x0000000000000005 (STRTAB)             0x14d20
0x0000000000000006 (SYMTAB)             0x4e68
0x000000000000000a (STRSZ)              143265 (bytes)
0x000000000000000b (SYMENT)             24 (bytes)
0x0000000000000003 (PLTGOT)             0x3b0000
0x0000000000000002 (PLTRELSZ)           29616 (bytes)
0x0000000000000014 (PLTREL)             RELA
0x0000000000000017 (JMPREL)             0x45270
0x0000000000000007 (RELA)               0x393c0
0x0000000000000008 (RELASZ)             48816 (bytes)
0x0000000000000009 (RELAENT)            24 (bytes)
0x000000006ffffffe (VERNEED)            0x39200
0x000000006fffffff (VERNEEDNUM)         7
0x000000006ffffff0 (VERSYM)             0x37cc2
0x000000006ffffff9 (RELACOUNT)          680
0x0000000000000000 (NULL)               0x0
""".lstrip()
        return library

    assert deps.use_readelf_to_determine_deps(
        "foo.so", run_readelf_strategy=dummy_readelf
    ) == ["bar.so"]


def test_fix_up_darwin_libraries_empty():
    deploy_library_strat = Mock()
    change_depend_shared_lib_name_strat = Mock()
    get_dependencies_strat = Mock(return_value=[])
    deps.fix_up_darwin_libraries(
        "openjp2",
        search_paths=[],
        get_dependencies_strat=get_dependencies_strat,
        change_depend_shared_lib_name_strat=(
            change_depend_shared_lib_name_strat
        ),
        deploy_library_strat=deploy_library_strat
    )
    deploy_library_strat.assert_not_called()


def test_fix_up_darwin_libraries(monkeypatch):
    deploy_library_strat = Mock()
    get_dependencies_strat = Mock(return_value=[("/some/path", "zstd")])
    monkeypatch.setattr(deps.os.path, "exists", lambda p: "fake_path" in p)
    deps.fix_up_darwin_libraries(
        "openjp2",
        search_paths=["fake_path"],
        get_dependencies_strat=get_dependencies_strat,
        change_depend_shared_lib_name_strat=Mock(
            name="change_depend_shared_lib_name_strat"
        ),
        deploy_library_strat=deploy_library_strat
    )
    deploy_library_strat.assert_called_once_with(
        os.path.join("fake_path", "zstd"), "zstd", ANY

    )


def test_otool_subprocess(monkeypatch):
    run = Mock()
    monkeypatch.setattr(deps.subprocess, "run", run)
    deps.otool_subprocess("openjp2", "otool_exec")
    assert run.call_args[0][0] == ["otool_exec", "-L", "openjp2"]


@pytest.mark.parametrize(
    "library_name, otool_output, expected_list",
    [
        (
            "/Users/testUser/.conan2/p/b/tessec2b892a8fd9b9/p/lib/libtesseract.5.5.0.dylib",
            """
/Users/testUser/.conan2/p/b/tessec2b892a8fd9b9/p/lib/libtesseract.5.5.0.dylib:
@rpath/libtesseract.5.5.dylib (compatibility version 5.5.0, current version 5.5.0)
/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1351.0.0)
@rpath/libleptonica.6.dylib (compatibility version 6.0.0, current version 6.0.0)
/usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 1900.180.0)
""".lstrip(),
            [("@rpath", "libtesseract.5.5.dylib"),
             ("@rpath", "libleptonica.6.dylib")]
        ),
        (
            "/usr/local/opt/imagemagick/lib/libMagick++-7.Q16HDRI.5.dylib",
            """
/usr/local/opt/imagemagick/lib/libMagick++-7.Q16HDRI.5.dylib (compatibility version 6.0.0, current version 6.0.0)
/usr/local/Cellar/imagemagick/7.1.2-0/lib/libMagickCore-7.Q16HDRI.10.dylib (compatibility version 11.0.0, current version 11.2.0)
/usr/local/Cellar/imagemagick/7.1.2-0/lib/libMagickWand-7.Q16HDRI.10.dylib (compatibility version 11.0.0, current version 11.2.0)
/usr/local/opt/little-cms2/lib/liblcms2.2.dylib (compatibility version 3.0.0, current version 3.17.0)
/usr/local/opt/liblqr/lib/liblqr-1.0.dylib (compatibility version 4.0.0, current version 4.2.0)
/usr/local/opt/glib/lib/libglib-2.0.0.dylib (compatibility version 8401.0.0, current version 8401.3.0)
/usr/local/opt/gettext/lib/libintl.8.dylib (compatibility version 13.0.0, current version 13.4.0)
/usr/lib/libxml2.2.dylib (compatibility version 10.0.0, current version 10.9.0)
/usr/local/opt/fontconfig/lib/libfontconfig.1.dylib (compatibility version 17.0.0, current version 17.0.0)
/usr/local/opt/freetype/lib/libfreetype.6.dylib (compatibility version 27.0.0, current version 27.2.0)
/usr/lib/libbz2.1.0.dylib (compatibility version 1.0.0, current version 1.0.8)
/usr/lib/libz.1.dylib (compatibility version 1.0.0, current version 1.2.12)
/usr/local/opt/libtool/lib/libltdl.7.dylib (compatibility version 11.0.0, current version 11.3.0)
/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1345.120.2)
/usr/local/opt/libomp/lib/libomp.dylib (compatibility version 5.0.0, current version 5.0.0)
/usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 1700.255.5)
""".lstrip(),
            [
                (
                    "/usr/local/Cellar/imagemagick/7.1.2-0/lib",
                    "libMagickCore-7.Q16HDRI.10.dylib"
                ),
                (
                    "/usr/local/Cellar/imagemagick/7.1.2-0/lib",
                    "libMagickWand-7.Q16HDRI.10.dylib"
                ),
                ("/usr/local/opt/little-cms2/lib", "liblcms2.2.dylib"),
                ("/usr/local/opt/liblqr/lib", "liblqr-1.0.dylib"),
                ("/usr/local/opt/glib/lib", "libglib-2.0.0.dylib"),
                ("/usr/local/opt/gettext/lib", "libintl.8.dylib"),
                ("/usr/local/opt/fontconfig/lib", "libfontconfig.1.dylib"),
                ("/usr/local/opt/freetype/lib", "libfreetype.6.dylib"),
                ("/usr/local/opt/libtool/lib", "libltdl.7.dylib"),
                ("/usr/local/opt/libomp/lib", "libomp.dylib"),
            ]
        )
    ]
)
def test_iter_otool_lib_dependencies(
        library_name,
        otool_output,
        expected_list
):
    assert list(deps.iter_otool_lib_dependencies(
        library_name,
        otool_get_shared_libs_strategy=lambda *_: otool_output
    )) == expected_list


def test_change_mac_lib_shared_library_name(monkeypatch):
    check_call = Mock()
    monkeypatch.setattr(deps.subprocess, "check_call", check_call)
    deps.change_mac_lib_depend_shared_lib_name(
        "build/myproject/libspamuser.so",
        "/usr/local/opt/spam/libspam.5.5.dylib",
        "eggs.dylib",
        "/usr/bin/install_name_tool"
    )
    assert check_call.call_args[0][0] == [
        "/usr/bin/install_name_tool",
        "-change",
        "/usr/local/opt/spam/libspam.5.5.dylib",
        os.path.join("@loader_path", "eggs.dylib"),
        "build/myproject/libspamuser.so"
    ]


def test_iter_otool_lib_dependencies_get_bad_parse():
    with pytest.raises(ValueError) as e:
        list(deps.iter_otool_lib_dependencies(
            "spam",
            otool_get_shared_libs_strategy=lambda *_: "bad unparsible output"
        ))
    assert "unable to parse" in str(e)


def test_run_patchelf_needed(monkeypatch):
    run = Mock()
    deps.run_patchelf_needed("libspam", "patchelf", run)
    run.assert_called_with(["patchelf", "--print-needed", "libspam"])


@pytest.mark.parametrize(
    "library, expected",
    [
        ("libspam", False),
        ("libm", True),
    ]
)
def test_is_linux_system_libraries(library, expected):
    assert deps.is_linux_system_libraries(library) == expected


def test_deploy_darwin_shared_lib(monkeypatch):
    copy2 = Mock()
    monkeypatch.setattr(deps.shutil, "copy2", copy2)
    fix_up_strategy = Mock()
    deps.deploy_darwin_shared_lib("start", "dest", fix_up_strategy)
    fix_up_strategy.assert_called_once_with("dest")


class TestFixUpWindowsLibraries:
    def test_get_dependencies(self):
        fixer = deps.FixUpWindowsLibraries([])
        fixer.dependency_search_strategy = Mock()
        fixer.get_dependencies("zstd.dll")
        fixer.dependency_search_strategy.assert_called_once_with("zstd.dll")

    def test_find_shared_library(self, monkeypatch):
        fixer = deps.FixUpWindowsLibraries(["spam_path"])
        monkeypatch.setattr(
            deps.os.path,
            "exists",
            lambda p: os.path.join("spam_path", "zstd.dll")
        )
        assert fixer.find_shared_library("zstd.dll") ==\
               os.path.join("spam_path", "zstd.dll")

    def test_deploy_and_fixup_library(self):
        fixer = deps.FixUpWindowsLibraries(["spam_path"])
        fixer.deploy = Mock()
        fixer.fix_up = Mock()
        fixer.deploy_and_fixup_library("spam_path/zstd.dll", "dest/zstd.dll")

        fixer.deploy.assert_called()
        fixer.fix_up.assert_called()

    def test_fix_up(self):
        fixer = deps.FixUpWindowsLibraries(["spam_path"])
        fixer.deploy = Mock()
        fixer.deploy_and_fixup_library = Mock()
        fixer.find_shared_library = Mock(return_value="zstd.dll")
        fixer.get_dependencies =\
            Mock(return_value=["zstd.dll", "KERNEL32.dll"])

        fixer.fix_up(os.path.join("spam_path", "eggs.pyd"))

        fixer.deploy_and_fixup_library.assert_called_once_with(
            "zstd.dll", os.path.join("spam_path", "zstd.dll")
        )

    def test_fix_up_missing_file(self):
        fixer = deps.FixUpWindowsLibraries(["spam_path"])
        fixer.deploy = Mock()
        fixer.deploy_and_fixup_library = Mock()
        fixer.find_shared_library = Mock(return_value=None)
        fixer.get_dependencies =\
            Mock(return_value=["zstd.dll", "KERNEL32.dll"])

        with pytest.raises(FileNotFoundError):
            fixer.fix_up(os.path.join("spam_path", "eggs.pyd"))

    def test_fix_up_skips_existing(self, monkeypatch):
        fixer = deps.FixUpWindowsLibraries(["spam_path"])
        fixer.deploy = Mock()
        fixer.deploy_and_fixup_library = Mock()
        fixer.get_dependencies = Mock(
            return_value=["zstd.dll", "zlib.dll", "KERNEL32.dll"]
        )
        fixer.find_shared_library = lambda x: x
        with monkeypatch.context() as m:
            # simulate that zlib.dll already exists
            m.setattr(
                deps.os.path,
                "exists",
                lambda p: p == os.path.join("spam_path", "zlib.dll")
            )
            fixer.fix_up(os.path.join("spam_path", "eggs.pyd"))

        fixer.deploy_and_fixup_library.assert_called_once_with(
            "zstd.dll", os.path.join("spam_path", "zstd.dll")
        )


def test_fix_up_windows_libraries():
    fixup_obj = Mock(spec_set=deps.FixUpWindowsLibraries)
    fixup_klass = Mock(return_value=fixup_obj)
    deps.fix_up_windows_libraries(
        "openjp2",
        search_paths=["fake_path"],
        exclude_libraries=["some_system_lib.dll"],
        fixup_klass=fixup_klass
    )
    fixup_klass.assert_called_once_with(["fake_path"], exclude_libraries=["some_system_lib.dll"])
    fixup_obj.fix_up.assert_called_once_with("openjp2")