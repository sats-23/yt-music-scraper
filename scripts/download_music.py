import csv
import os
import shutil
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Always resolve paths relative to the project root so the script works both
# when called as a subprocess by server.py (cwd=root) and when run standalone.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSV_FILE = os.path.join(ROOT, "results.csv")
DOWNLOAD_DIR = os.path.join(ROOT, "Music")
YT_DLP = os.path.join(ROOT, "yt-dlp")

MAX_PARALLEL_DOWNLOADS = 5
MAX_RETRIES = 3

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Ensure PATH includes standard Homebrew and local binary directories
env_path = os.environ.get("PATH", "")
extra_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
for p in extra_paths:
    if p not in env_path.split(os.pathsep):
        env_path = f"{p}{os.pathsep}{env_path}"
CUSTOM_ENV = dict(os.environ, PATH=env_path)

FFMPEG_BIN = shutil.which("ffmpeg", path=env_path)


def download_song(row):
    song_name = row.get("Song", "Unknown_Song")
    url_blob = row.get("YouTube URL", "")

    if not url_blob or url_blob.strip().lower() in ("none", ""):
        return f"[SKIPPED] No URL for {song_name}"

    target_url = url_blob.strip().splitlines()[0].strip()

    # Clean filename (removes : / \ etc.)
    clean_name = "".join(c for c in song_name if c.isalnum() or c in (" ", "-", "_")).strip()

    for attempt in range(MAX_RETRIES):
        try:
            print(f"[STARTING] {song_name} (attempt {attempt + 1})\n")
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
                "--output", os.path.join(DOWNLOAD_DIR, clean_name + ".%(ext)s"),
                "--no-playlist",
            ]
            if FFMPEG_BIN:
                cmd.extend(["--ffmpeg-location", os.path.dirname(FFMPEG_BIN)])
            cmd.append(target_url)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=ROOT,
                env=CUSTOM_ENV,
            )
            if result.returncode == 0:
                return f"[FINISHED] {song_name}\n"
            else:
                if attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** attempt
                    print(f"[RETRY] {song_name} failed (attempt {attempt + 1}), retrying in {wait_time}s...\n")
                    time.sleep(wait_time)
                else:
                    error_msg = result.stderr if result.stderr else "Unknown error"
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200] + "..."
                    return f"[ERROR] {song_name}: yt-dlp returned {result.returncode}. Stderr: {error_msg}\n"
        except subprocess.TimeoutExpired:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                print(f"[RETRY] {song_name} timed out (attempt {attempt + 1}), retrying in {wait_time}s...\n")
                time.sleep(wait_time)
            else:
                return f"[ERROR] {song_name}: Timeout after {MAX_RETRIES} attempts\n"
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                print(f"[RETRY] {song_name} failed (attempt {attempt + 1}) with exception: {e}, retrying in {wait_time}s...\n")
                time.sleep(wait_time)
            else:
                return f"[ERROR] {song_name}: {str(e)}\n"


def run_parallel():
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        songs_to_download = list(csv.DictReader(f))

    print(f"Found {len(songs_to_download)} tracks. Downloading audio streams...\n")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_DOWNLOADS) as executor:
        results = list(executor.map(download_song, songs_to_download))

    print("\n--- Process Complete ---")
    for res in results:
        print(res)


if __name__ == "__main__":
    run_parallel()
