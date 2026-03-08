import csv
import os
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

# Configuration
CSV_FILE = 'results.csv'
DOWNLOAD_DIR = 'Music'
MAX_PARALLEL_DOWNLOADS = 5 

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
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_DIR}/{clean_name}.%(ext)s',
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # Forces FFmpeg to ignore missing metadata/headers in the stream
        'postprocessor_args': [
            '-err_detect', 'ignore_err'
        ],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        print(f"[STARTING] {song_name}\n")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])
        return f"[FINISHED] {song_name}\n"
    except Exception as e:
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