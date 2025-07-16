from typing import Optional, List
import os

__all__ = ["locate_file"]


def locate_file(file_name: str, search_locations: List[str]) -> Optional[str]:
    for location in search_locations:
        candidate = os.path.join(location, file_name)
        if os.path.exists(candidate):
            return candidate
    return None
