import contextlib
from typing import Optional, List, Dict
import os

__all__ = ["locate_file"]


def locate_file(file_name: str, search_locations: List[str]) -> Optional[str]:
    """Locate a file in the given search locations."""
    for location in search_locations:
        candidate = os.path.join(location, file_name)
        if os.path.exists(candidate):
            return candidate
    return None


@contextlib.contextmanager
def set_env_var(env_vars: Dict[str, str]):
    """Set an environment variable."""
    og_env = os.environ.copy()
    os.environ.update(**env_vars)

    yield

    # Do not assign os.environ to og_env because it makes os.environ
    # case-sensitive, even on OSs that have case-insensitive environment
    # variables such as windows. When this happens it makes it hard to use
    # os.environ and breaks setuptools trying to find Visual Studio.

    # Remove any keys that were set since entering the context
    for k in [
        k for k in os.environ.keys()
        if k not in og_env
    ]:
        del os.environ[k]

    # set the values of environment variables before entering the context
    for k, v in og_env.items():
        os.environ[k] = v
