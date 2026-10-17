# YouTube Music Scraper

Search YouTube for a list of songs, download them as MP3, and tidy the filenames — all in one command.

## Prerequisites

1. **Python 3** — check with `python3 --version`
2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **yt-dlp binary** — place the `yt-dlp` executable in the project root and make it runnable:
   ```bash
   chmod +x yt-dlp
   ```
   Download it from https://github.com/yt-dlp/yt-dlp/releases
4. **ffmpeg** — used to convert downloads to MP3. The project falls back to the version bundled inside the `imageio-ffmpeg` package (installed above), so this works out of the box. For better results, install it system-wide:
   ```bash
   brew install ffmpeg   # macOS
   ```

## How to run

### Option A — Web UI (easiest)

```bash
python3 server.py
```

A browser tab opens at http://localhost:8000 automatically.  
Paste one song per line (e.g. `The Beatles - Hey Jude`), press **Start**, and watch the progress.  
Finished MP3s are saved in the `Music/` folder.

### Option B — Command line

Pass song names as arguments:

```bash
python3 -m pipeline "The Beatles - Hey Jude" "Queen - Bohemian Rhapsody"
```

Or pipe them in, one per line:

```bash
printf 'Daft Punk - Get Lucky\nABBA - Dancing Queen\n' | python3 -m pipeline
```

MP3s are saved to `Music/` in the project root.

## What happens under the hood

The pipeline runs three stages in order:

```
Search  →  Download  →  Rename
```

1. **Search** — looks up each song on YouTube in parallel, fetches the top 8 results, and picks the one best suited for listening (prefers "- Topic" channels, "Official Audio" and "Lyrics" uploads; avoids music videos, live versions, covers, remixes, and wrong-artist matches).
2. **Download** — uses `yt-dlp` + `ffmpeg` to download the audio and convert it to MP3.
3. **Rename** — reads the ID3 tags written by `yt-dlp` and renames each file to `Artist - Title.mp3`.

No temporary files are written between stages — data is passed directly in memory.

## Project layout

```
yt-music-scraper/
├── server.py          Web UI backend (runs the pipeline, exposes progress over HTTP)
├── index.html         Web UI frontend
├── yt-dlp             yt-dlp binary (you provide this)
├── requirements.txt   Python dependencies
├── Music/             Downloaded MP3s end up here
└── pipeline/
    ├── __init__.py    Exports search_all, download_all, rename_music_files
    ├── __main__.py    CLI entry point  (python3 -m pipeline …)
    ├── common.py      Shared paths (MUSIC_DIR, YT_DLP) and subprocess helper
    ├── search.py      search_all(songs)        → [(song, url), …]
    ├── download.py    download_all(rows)        → [(song, ok, message), …]
    └── rename.py      rename_music_files(dir)  → [(file, status, detail), …]
```

## Stopping a run

- **Web UI** — click the **Cancel** button.
- **CLI** — press `Ctrl+C`.
