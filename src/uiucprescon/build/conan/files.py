"""Handling files related to Conan."""

import dataclasses
import io
import os
import json
from typing import List, Dict, TypedDict, Iterable, Optional, Tuple, Set
import abc
import warnings
from uiucprescon.build.utils import locate_file

__all__ = [
    "parse_conan_build_info",
    "read_conan_build_info_json",
    "get_library_metadata_from_build_info_json",
    "get_linking_libraries_fp",
    "ConanBuildInfo"
]


class ConanBuildInfoParser:
    def __init__(self, fp: io.TextIOWrapper) -> None:
        self._fp = fp

    def parse(self) -> Dict[str, List[str]]:
        data = {}
        for subject_chunk in self.iter_subject_chunk():
            subject_title = subject_chunk[0][1:-1]

            data[subject_title] = subject_chunk[1:]
        return data

    def iter_subject_chunk(self) -> Iterable[List[str]]:
        buffer: List[str] = []
        for line in self._fp:
            line = line.strip()
            if len(line) == 0:
                continue
            if line.startswith("[") and line.endswith("]") and buffer:
                yield buffer
                buffer.clear()
            buffer.append(line)
        yield buffer
        buffer.clear()


class ConanLibraryMetadata(TypedDict):
    libs: List[str]
    includedirs: List[str]
    libdirs: List[str]
    bindirs: List[str]
    resdirs: List[str]
    builddirs: List[str]
    system_libs: List[str]
    defines: List[str]
    cppflags: List[str]
    cxxflags: List[str]
    cflags: List[str]
    sharedlinkflags: List[str]
    exelinkflags: List[str]
    sysroot: List[str]
    frameworks: List[str]
    frameworkdirs: List[str]
    rootpath: List[str]
    name: str
    version: Optional[str]
    generatornames: List[str]
    generatorfilenames: List[str]


class ConanBuildInfo(TypedDict):
    """Conan build info data structure."""

    definitions: List[str]
    include_paths: List[str]
    lib_paths: List[str]
    bin_paths: List[str]
    libs: List[str]
    metadata: Dict[str, ConanLibraryMetadata]


class AbsConanBuildInfo(abc.ABC):
    @abc.abstractmethod
    def parse(self, filename: str) -> ConanBuildInfo:
        pass


class ConanBuildInfoTXT(AbsConanBuildInfo):
    def parse(self, filename: str) -> ConanBuildInfo:
        with open(filename, "r", encoding="utf-8") as f:
            parser = ConanBuildInfoParser(f)
            data = parser.parse()
            definitions = data["defines"]
            include_paths = data["includedirs"]
            lib_paths = data["libdirs"]
            bin_paths = data["bindirs"]
            libs = data["libs"]
            names: List[str] = [
                value.replace("name_", "")
                for value in data
                if value.startswith("name_")
            ]
            # print(names)
            libsmetadata: Dict[str, ConanLibraryMetadata] = {}
            for library_name in names:
                version = data.get(f"version_{library_name}", None)
                libsmetadata[library_name] = {
                    "libs": data.get(f"libs_{library_name}", []),
                    "includedirs": data.get(f"includedirs_{library_name}", []),
                    "libdirs": data.get(f"libdirs_{library_name}", []),
                    "bindirs": data.get(f"bindirs_{library_name}", []),
                    "resdirs": data.get(f"resdirs_{library_name}", []),
                    "builddirs": data.get(f"builddirs_{library_name}", []),
                    "system_libs": data.get(f"system_libs_{library_name}", []),
                    "defines": data.get(f"defines_{library_name}", []),
                    "cppflags": data.get(f"cppflags_{library_name}", []),
                    "cxxflags": data.get(f"cxxflags_{library_name}", []),
                    "cflags": data.get(f"cflags_{library_name}", []),
                    "sharedlinkflags": data.get(
                        f"sharedlinkflags_{library_name}", []
                    ),
                    "exelinkflags": data.get(
                        f"exelinkflags_{library_name}", []
                    ),
                    "sysroot": data.get(f"sysroot_{library_name}", []),
                    "frameworks": data.get(f"frameworks_{library_name}", []),
                    "frameworkdirs": data.get(
                        f"frameworkdirs_{library_name}", []
                    ),
                    "rootpath": data.get(f"rootpath_{library_name}", []),
                    "name": library_name,
                    "version": version[0] if version else None,
                    "generatornames": data.get(
                        f"generatornames_{library_name}", []
                    ),
                    "generatorfilenames": data.get(
                        f"generatorfilenames_{library_name}", []
                    ),
                }
        return {
            "definitions": definitions,
            "include_paths": list(include_paths),
            "lib_paths": list(lib_paths),
            "bin_paths": list(bin_paths),
            "libs": list(libs),
            "metadata": libsmetadata,
        }


def locate_conanbuildinfo(search_locations: List[str]) -> Optional[str]:
    warnings.warn(
        message="use uiucprescon.build.utils.locate_file() instead",
        category=DeprecationWarning,
    )
    return locate_file("conanbuildinfo.txt", search_locations)


def locate_conanbuildinfo_json(search_locations: List[str]) -> Optional[str]:
    warnings.warn(
        message="use uiucprescon.build.utils.locate_file() instead",
        category=DeprecationWarning,
    )
    return locate_file("conanbuildinfo.json", search_locations)


@dataclasses.dataclass
class CLibCompilerMetadata:
    include_paths: List[str] = dataclasses.field(default_factory=list)
    definitions: List[Tuple[str, Optional[str]]] =\
        dataclasses.field(default_factory=list)
    lib_dirs: List[str] = dataclasses.field(default_factory=list)
    bin_paths: List[str] = dataclasses.field(default_factory=list)
    libs: List[str] = dataclasses.field(default_factory=list)


def locate_node_by_id(reference_key, nodes):
    for node_key, node in nodes.items():
        if node_key == reference_key:
            return node
    return None


def _locate_node_by_name(name, nodes):
    for node_key, node in nodes.items():
        if node.get('name') == name:
            return node_key, node
        if cpp_info := node.get('cpp_info'):
            root = cpp_info.get('root')
            if root:
                for lib in (root.get('libs') or []):
                    if lib == name:
                        return node_key, node
    return None, None


def get_linking_libraries_fp(
    library_name: str,
    conan_build_info_fp: io.TextIOWrapper
) -> List[str]:
    """Get the linking libraries for a library from a Conan build info file."""
    original_position = conan_build_info_fp.tell()
    try:
        data = json.load(conan_build_info_fp)
        _, node = _locate_node_by_name(library_name, data['graph']['nodes'])
        libs = []
        for cpp_info in node['cpp_info'].values():
            libs += cpp_info.get('libs', []) or []
        return libs
    finally:
        conan_build_info_fp.seek(original_position)


def _get_from_ref(reference_key: str, nodes) -> CLibCompilerMetadata:
    metadata = CLibCompilerMetadata()
    node = locate_node_by_id(reference_key, nodes)
    if not node:
        raise ValueError(f"Node with {reference_key} not found")

    for data in node.get('cpp_info', {}).values():
        metadata.include_paths += [
            include_path for include_path
            in data.get("includedirs", []) or []
            if all([
                include_path not in metadata.include_paths,
                os.path.exists(include_path)
            ])
        ]

        metadata.definitions += [
            (define, None) for define in data.get("defines", []) or []
            if (define, None) not in metadata.definitions
        ]

        metadata.lib_dirs += [
            lib_dir for lib_dir in data.get("libdirs", []) or []
            if all([
                lib_dir not in metadata.lib_dirs,
                os.path.exists(lib_dir)
            ])
        ]

        metadata.bin_paths += [
            bindir for bindir in data.get("bindirs", []) or []
            if all([
                bindir not in metadata.bin_paths,
                os.path.exists(bindir)
            ])
        ]
        for lib in (data.get("libs", []) or []):
            if lib not in metadata.libs:
                metadata.libs.append(lib)
            else:
                del metadata.libs[metadata.libs.index(lib)]
                metadata.libs.append(lib)
        for lib in (data.get("system_libs", []) or []):
            if lib not in metadata.libs:
                metadata.libs.append(lib)
            else:
                del metadata.libs[metadata.libs.index(lib)]
                metadata.libs.append(lib)

    for dep_key, dep_listing in node.get('dependencies', {}).items():
        if dep_listing["skip"] is True:
            continue
        dependency_metadata = _get_from_ref(dep_key, nodes)
        if dep_listing["headers"] is True:
            metadata.include_paths += [
                include_path for include_path in
                dependency_metadata.include_paths
                if all([
                    include_path not in metadata.include_paths,
                    os.path.exists(include_path)
                ])
            ]
        metadata.definitions += [
            define for define in dependency_metadata.definitions
            if define not in metadata.definitions
        ]
        if dep_listing['libs'] is True:
            metadata.lib_dirs += [
                lib_dir for lib_dir in dependency_metadata.lib_dirs
                if all([
                    lib_dir not in metadata.lib_dirs,
                    os.path.exists(lib_dir)
                ])
            ]

            for lib in dependency_metadata.libs:
                if lib not in metadata.libs:
                    metadata.libs.append(lib)
                    continue
                del metadata.libs[metadata.libs.index(lib)]
                metadata.libs.append(lib)

        metadata.bin_paths += [
            bindir for bindir in dependency_metadata.bin_paths
            if all([
                bindir not in metadata.bin_paths,
                os.path.exists(bindir)
            ])
        ]

    return metadata


def get_library_metadata_from_build_info_json(
    library_name, fp: io.TextIOWrapper
) -> Optional[CLibCompilerMetadata]:
    """Get the metadata for a library from a Conan build info JSON file."""
    metadata = CLibCompilerMetadata()
    original_position = fp.tell()
    try:
        fp.seek(0)
        try:
            data = json.load(fp)
        except json.JSONDecodeError as e:
            warnings.warn(
                f"Failed to parse JSON from {fp.name}: {e}",
                category=UserWarning,
            )
            return None
        nodes = data['graph']['nodes']
        key, node = _locate_node_by_name(library_name, nodes)
        if not node:
            return None
        node_data = _get_from_ref(key, nodes)

        for include_path in node_data.include_paths:
            if include_path not in metadata.include_paths:
                metadata.include_paths.append(include_path)
                # metadata.include_paths.insert(0, include_path)

        for definition in node_data.definitions:
            if definition not in metadata.definitions:
                metadata.definitions.append(definition)

        for lib_dir in node_data.lib_dirs:
            if lib_dir not in metadata.lib_dirs:
                metadata.lib_dirs.append(lib_dir)

        for lib in node_data.libs:
            if lib not in metadata.libs:
                metadata.libs.append(lib)
            else:
                del metadata.libs[metadata.libs.index(lib)]
                metadata.libs.append(lib)

        for bin_path in node_data.bin_paths:
            if bin_path not in metadata.bin_paths:
                metadata.bin_paths.append(bin_path)
        return metadata
    finally:
        fp.seek(original_position)


def read_conan_build_info_json(fp: io.TextIOWrapper):
    """Read a Conan build info JSON file and return the relevant data."""
    definitions: List[str] = []
    include_paths: List[str] = []
    lib_dirs: List[str] = []
    bin_paths: List[str] = []
    libs: List[str] = []
    data = json.loads(fp.read())
    for node in data['graph']['nodes'].values():
        if node.get('name') is None:
            continue
        for data in node.get('cpp_info', {}).values():
            include_paths += [
                include_path for include_path
                in data.get("includedirs", []) or []
                if all([
                    include_path not in include_paths,
                    os.path.exists(include_path)
                ])
            ]

            definitions += [
                define for define in data.get("defines", []) or []
                if define not in definitions
            ]

            lib_dirs += [
                lib_dir for lib_dir in data.get("libdirs", []) or []
                if all([
                    lib_dir not in lib_dirs,
                    os.path.exists(lib_dir)
                ])
            ]

            bin_paths += [
                bindir for bindir in data.get("bindirs", []) or []
                if all([
                    bindir not in bin_paths,
                    os.path.exists(bindir)
                ])
            ]

            libs += [
                lib for lib in data.get("libs", []) or []
                if lib not in libs
            ]
    return {
        "definitions": definitions,
        "include_paths": include_paths,
        "lib_paths": lib_dirs,
        "bin_paths": bin_paths,
        "libs": libs,
        "metadata": {},
    }


def parse_conan_build_info(
        conan_build_info_file: str, section: str
) -> Set[str]:
    """Parse a section from a Conan build info file."""
    items = set()
    with open(conan_build_info_file, encoding="utf-8") as f:
        found = False
        while True:
            line = f.readline()
            if not line:
                break
            if line.strip() == f"[{section}]":
                found = True
                continue
            if found:
                if line.strip() == "":
                    found = False
                    continue
                if found:
                    items.add(line.strip())
    return items
