from typing import List, Dict, TypedDict, Iterable, Any
import abc


class ConanBuildInfoParser:
    def __init__(self, fp):
        self._fp = fp

    def parse(self) -> Dict[str, List[str]]:
        data = {}
        for subject_chunk in self.iter_subject_chunk():
            subject_title = subject_chunk[0][1:-1]

            data[subject_title] = subject_chunk[1:]
        return data

    def iter_subject_chunk(self) -> Iterable[Any]:
        buffer = []
        for line in self._fp:
            line = line.strip()
            if len(line) == 0:
                continue
            if line.startswith("[") and line.endswith("]") and len(buffer) > 0:
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
    name: List[str]
    version: List[str]
    generatornames: List[str]
    generatorfilenames: List[str]


class AbsConanBuildInfo(abc.ABC):
    @abc.abstractmethod
    def parse(self, filename: str) -> Dict[str, str]:
        pass


class ConanBuildInfo(TypedDict):
    definitions: List[str]
    include_paths: List[str]
    lib_paths: List[str]
    bin_paths: List[str]
    libs: List[str]
    metadata: Dict[str, ConanLibraryMetadata]


class ConanBuildInfoTXT(AbsConanBuildInfo):

    def parse(self, filename: str) -> ConanBuildInfo:
        # def parse(self, filename: str) -> Dict[str, Union[str, List[str]]]:
        with open(filename, "r", encoding="utf-8") as f:
            parser = ConanBuildInfoParser(f)
            data = parser.parse()
            definitions = data['defines']
            include_paths = data['includedirs']
            lib_paths = data['libdirs']
            bin_paths = data['bindirs']
            libs = data['libs']
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
                    "system_libs":
                        data.get(f"system_libs_{library_name}", []),
                    "defines":
                        data.get(f"defines_{library_name}", []),
                    "cppflags":
                        data.get(f"cppflags_{library_name}", []),
                    "cxxflags":
                        data.get(f"cxxflags_{library_name}", []),
                    "cflags": data.get(f"cflags_{library_name}", []),
                    "sharedlinkflags":
                        data.get(f"sharedlinkflags_{library_name}", []),
                    "exelinkflags":
                        data.get(f"exelinkflags_{library_name}", []),
                    "sysroot": data.get(f"sysroot_{library_name}", []),
                    "frameworks":
                        data.get(f"frameworks_{library_name}", []),
                    "frameworkdirs":
                        data.get(f"frameworkdirs_{library_name}", []),
                    "rootpath": data.get(f"rootpath_{library_name}", []),
                    "name": library_name,
                    "version": version[0] if version else None,
                    "generatornames":
                        data.get(f"generatornames_{library_name}", []),
                    "generatorfilenames":
                        data.get(f"generatorfilenames_{library_name}", []),
                }
        return {
            "definitions": definitions,
            "include_paths": list(include_paths),
            "lib_paths": list(lib_paths),
            "bin_paths": list(bin_paths),
            "libs": list(libs),
            "metadata": libsmetadata

        }
