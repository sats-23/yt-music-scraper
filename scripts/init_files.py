#!/usr/bin/env python3
"""
init_files.py — project setup helper.

Called automatically by server.py on startup, and can also be run standalone:
    python3 scripts/init_files.py

Creates (if missing):
    songs.txt     — empty song list, one song per line
    results.csv   — CSV with header Song,YouTube URL
    Music/        — output directory for downloaded MP3s
"""
import os

# Always resolve paths relative to the project root (parent of this script).
# This works correctly both when imported by server.py and when run directly.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "songs.txt": "",
    "results.csv": "Song,YouTube URL\n",
}
DIRS = ["Music"]


def ensure(verbose=False):
    """Create any missing project files/dirs. Safe to call repeatedly."""
    created = []

    for name, content in FILES.items():
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            created.append(name)

    for name in DIRS:
        path = os.path.join(ROOT, name)
        if not os.path.isdir(path):
            os.makedirs(path)
            created.append(name + "/")

    if verbose and created:
        print("Initialised:", ", ".join(created))


def main():
    """Standalone entry-point — prints a full report."""
    created = []
    skipped = []

    for name, content in FILES.items():
        path = os.path.join(ROOT, name)
        if os.path.exists(path):
            skipped.append(name)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            created.append(name)

    for name in DIRS:
        path = os.path.join(ROOT, name)
        if os.path.isdir(path):
            skipped.append(name + "/")
        else:
            os.makedirs(path)
            created.append(name + "/")

    if created:
        print("Created:")
        for item in created:
            print(f"  ✔  {item}")
    if skipped:
        print("Already exists (skipped):")
        for item in skipped:
            print(f"  –  {item}")

    print("\nDone.")


if __name__ == "__main__":
    main()
