"""CLI: python3 -m pipeline "Artist - Song" "Another Song"   (or pipe song names via stdin)"""
import sys

from . import download_all, rename_music_files, search_all
from .common import MUSIC_DIR


def main():
    songs = [s.strip() for s in (sys.argv[1:] or sys.stdin.read().splitlines()) if s.strip()]
    if not songs:
        sys.exit("Usage: python3 -m pipeline SONG [SONG ...]   (or one song per line on stdin)")

    rows = search_all(songs, on_result=lambda s, u: print(f"{s} -> {u}"))
    outcome = download_all(
        [r for r in rows if r[1]],
        on_finish=lambda s, ok, m: print(f"[{'FINISHED' if ok else 'ERROR'}] {s}" + ("" if ok else f": {m}")),
    )
    if any(ok for _, ok, _ in outcome):
        rename_music_files(MUSIC_DIR, on_result=lambda f, st, d: print(f"{f} [{st}] {d}".strip()))


if __name__ == "__main__":
    main()
