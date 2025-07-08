import io
import os
import json
from typing import List, Dict, TypedDict, Iterable, Optional
import abc
import warnings
from uiucprescon.build.utils import locate_file


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


def _get_from_ref(reference_key: str, nodes):
    include_paths = []
    definitions = []
    lib_dirs = []
    bin_paths = []
    libs = []
    for node_key, node in nodes.items():
        if node_key != reference_key:
            continue
        for dep_key, dep in node.get('dependencies', {}).items():
            data = _get_from_ref(dep_key, nodes)
            include_paths += [
                include_path for include_path
                in data.get("include_paths", []) or []
                if all([
                    include_path not in include_paths,
                    os.path.exists(include_path)
                ])
            ]

            definitions += [
                define for define in data.get("definitions", []) or []
                if define not in definitions
            ]

            lib_dirs += [
                lib_dir for lib_dir in data.get("lib_paths", []) or []
                if all([
                    lib_dir not in lib_dirs,
                    os.path.exists(lib_dir)
                ])
            ]

            bin_paths += [
                bindir for bindir in data.get("bin_paths", []) or []
                if all([
                    bindir not in bin_paths,
                    os.path.exists(bindir)
                ])
            ]

            libs += [
                lib for lib in data.get("libs", []) or []
                if lib not in libs
            ]

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
            libs += [
                lib for lib in data.get("system_libs", []) or []
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


def get_library_metadata_from_build_info_json(
    library_name, fp: io.TextIOWrapper
):
    definitions: List[str] = []
    include_paths: List[str] = []
    lib_dirs: List[str] = []
    bin_paths: List[str] = []
    libs: List[str] = []
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
        found = False
        for key, node in data['graph']['nodes'].items():
            if node.get('name') is None or node.get('name') != library_name:
                continue
            found = True
            node_data = _get_from_ref(key, data['graph']['nodes'])
            for include_path in reversed(node_data.get('include_paths', [])):
                if include_path not in include_paths:
                    include_paths.append(include_path)

            for definition in reversed(node_data.get('defines', [])):
                if definition not in definitions:
                    definitions.append(definition)

            for lib_dir in reversed(node_data.get('lib_paths', [])):
                if lib_dir not in lib_dirs:
                    lib_dirs.append(lib_dir)

            for lib in reversed(node_data.get('libs', [])):
                if lib not in libs:
                    libs.append(lib)

            for bin_path in reversed(node_data.get('bin_paths', [])):
                if bin_path not in bin_paths:
                    bin_paths.append(bin_path)
        if not found:
            return None
        return {
            "definitions": definitions,
            "include_paths": include_paths,
            "lib_paths": lib_dirs,
            "bin_paths": bin_paths,
            "libs": libs,
            "metadata": {},
        }
    finally:
        fp.seek(original_position)


def read_conan_build_info_json(fp: io.TextIOWrapper):
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
