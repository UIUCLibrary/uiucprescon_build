from importlib.metadata import version as _version
if _version('conan')[0] == "2":
    from . import v2 as conan_api
else:
    from . import v1 as conan_api

__all__ = ['conan_api']
