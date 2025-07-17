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