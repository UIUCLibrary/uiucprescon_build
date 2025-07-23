"""This module provides access to the Conan API."""
from importlib.metadata import version as _version
if _version('conan') < "2.0":
    from . import v1 as conan_api  # type: ignore[no-redef]
else:
    from . import v2 as conan_api
del _version

__all__ = ['conan_api']
