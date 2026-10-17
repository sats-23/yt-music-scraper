#!/usr/bin/env python3
"""
init_files.py — first-time project setup helper.

Run once from the project root before using the pipeline:
    python3 scripts/init_files.py

Creates (if missing):
    songs.txt     — empty song list, one song per line
    results.csv   — CSV with headers Song,YouTube URL
    Music/        — output directory for downloaded MP3s
"""
import csv
import os

# Always resolve paths relative to the project root (parent of this script)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "songs.txt": "",
    "results.csv": "Song,YouTube URL\n",
}
DIRS = ["Music"]


def main():
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

    print("\nDone. You can now run:  python3 server.py")


if __name__ == "__main__":
    main()
