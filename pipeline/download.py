import os
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            # Jitter prevents all concurrent retries from hitting the server at the same instant.
            time.sleep(2 ** attempt + random.uniform(0, 1))
    return False, error


def download_all(rows, on_start=None, on_finish=None, cancel=None):
    """Download [(song, url), ...] in parallel.

    `on_start(song)` / `on_finish(song, ok, message)` are called as work progresses.
    Returns [(song, ok, message), ...] in input order.

    Guarantees:
    - Always returns a full list (one entry per song), even when some downloads
      fail or raise unexpectedly — never raises from a worker exception.
    - Rows with no URL are short-circuited without occupying a thread slot.
    - Respects `cancel` before submitting each task, not only inside the worker.
    """
    if not rows:
        return []

    # Pre-populate so positions are stable even if futures finish out of order.
    results = [(song, False, "No URL") for song, _ in rows]

    def work(idx, song, url):
        if cancel and cancel.is_set():
            return idx, song, False, "Cancelled"
        if on_start:
            on_start(song)
        ok, msg = download_song(song, url, cancel)
        if on_finish:
            on_finish(song, ok, msg)
        return idx, song, ok, msg

    workers = min(MAX_PARALLEL_DOWNLOADS, sum(1 for _, url in rows if url))
    if workers == 0:
        return results

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(work, i, song, url): i
            for i, (song, url) in enumerate(rows)
            if url  # skip no-URL rows; they already have the right default
        }
        for fut in as_completed(futures):
            try:
                idx, song, ok, msg = fut.result()
            except Exception as exc:  # noqa: BLE001
                idx = futures[fut]
                song = rows[idx][0]
                ok, msg = False, str(exc)
                if on_finish:
                    on_finish(song, ok, msg)
            results[idx] = (song, ok, msg)

    return results
