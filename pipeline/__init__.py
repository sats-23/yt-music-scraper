"""Search -> download -> rename pipeline. Stages exchange data as Python objects."""
from .search import search_all
from .download import download_all
from .rename import rename_music_files

__all__ = ["search_all", "download_all", "rename_music_files"]
