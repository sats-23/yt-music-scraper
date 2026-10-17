import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from .common import FFMPEG_BIN, MUSIC_DIR, YT_DLP, run

MAX_PARALLEL_DOWNLOADS = 5
MAX_RETRIES = 3


def clean_name(song):
    """Filename stem used for a song (removes : / \\ etc.)."""
    return "".join(c for c in song if c.isalnum() or c in (" ", "-", "_")).strip()


def download_song(song, url, cancel=None):
    """Download one song as MP3. Returns (ok, message)."""
    if not url:
        return False, "No URL"
    os.makedirs(MUSIC_DIR, exist_ok=True)

    cmd = [
        YT_DLP,
        "--quiet",
        "--no-warnings",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--embed-metadata",
        "-f", "ba/b",
        "--extractor-args", "youtube:player_client=android,web",
        "--output", os.path.join(MUSIC_DIR, clean_name(song) + ".%(ext)s"),
        "--no-playlist",
    ]
    if FFMPEG_BIN:
        # A bundled binary isn't named plain "ffmpeg", so pass the file itself in that case
        is_plain = os.path.basename(FFMPEG_BIN) == "ffmpeg"
        cmd.extend(["--ffmpeg-location", os.path.dirname(FFMPEG_BIN) if is_plain else FFMPEG_BIN])
    cmd.append(url)

    error = "Unknown error"
    for attempt in range(MAX_RETRIES):
        if cancel and cancel.is_set():
            return False, "Cancelled"
        try:
            result = run(cmd, cancel=cancel, timeout=300)
            if result.returncode == 0:
                return True, "OK"
            if cancel and cancel.is_set():
                return False, "Cancelled"
            error = (result.stderr or "Unknown error").strip()[:200]
        except subprocess.TimeoutExpired:
            error = "Timeout"
        except Exception as e:  # noqa: BLE001
            error = str(e)
        if attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
    return False, error


def download_all(rows, on_start=None, on_finish=None, cancel=None):
    """Download [(song, url), ...] in parallel.

    `on_start(song)` / `on_finish(song, ok, message)` are called as work progresses.
    Returns [(song, ok, message), ...] in input order.
    """

    def work(row):
        song, url = row
        if on_start:
            on_start(song)
        ok, msg = download_song(song, url, cancel)
        if on_finish:
            on_finish(song, ok, msg)
        return song, ok, msg

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_DOWNLOADS) as ex:
        return list(ex.map(work, rows))
