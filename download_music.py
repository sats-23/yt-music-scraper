import csv
import os
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Configuration
CSV_FILE = 'results.csv'
DOWNLOAD_DIR = 'Music'
MAX_PARALLEL_DOWNLOADS = 5
MAX_RETRIES = 3

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def download_song(row):
    song_name = row.get('Song', 'Unknown_Song')
    url_blob = row.get('YouTube URL', '')
    
    if not url_blob:
        return f"[SKIPPED] No URL for {song_name}"

    urls = url_blob.strip().split('\n')
    if len(urls) < 2:
        target_url = urls[0].strip()
    else:
        target_url = urls[1].strip()

    # Clean filename (removes : / \ etc)
    clean_name = "".join([c for c in song_name if c.isalnum() or c in (' ', '-', '_')]).strip()
    
    for attempt in range(MAX_RETRIES):
        try:
            print(f"[STARTING] {song_name} (attempt {attempt + 1})\n")
            # Use local yt-dlp binary from project root
            binary_path = './yt-dlp'
            cmd = [
                binary_path,
                '--quiet',
                '--no-warnings',
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', '192K',
                '--output', f'{DOWNLOAD_DIR}/{clean_name}.%(ext)s',
                '--no-playlist',
                '--retries', '0',
                '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                '--sleep-interval', '0',
                '--postprocessor-args', '-err_detect ignore_err',
                target_url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                return f"[FINISHED] {song_name}\n"
            else:
                if attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** attempt
                    print(f"[RETRY] {song_name} failed (attempt {attempt + 1}), retrying in {wait_time}s...\n")
                    time.sleep(wait_time)
                else:
                    error_msg = result.stderr if result.stderr else 'Unknown error'
                    # Truncate error message to avoid too much output
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200] + '...'
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
    songs_to_download = []
    
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        songs_to_download = list(reader)

    print(f"Found {len(songs_to_download)} tracks. Downloading audio streams...\n")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_DOWNLOADS) as executor:
        results = list(executor.map(download_song, songs_to_download))

    print("\n--- Process Complete ---")
    for res in results:
        print(res)

if __name__ == "__main__":
    run_parallel()