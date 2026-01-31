# YouTube Music Scraper

A set of Python scripts to automate searching, downloading, and organizing music from YouTube.

## Prerequisites

1.  **Python 3**: Ensure you have Python 3 installed.
2.  **Dependencies**: Install the required Python packages:
    ```bash
    pip install requests mutagen
    ```
3.  **yt_dl Binary**: Ensure the `yt_dl` binary in this directory is executable:
    ```bash
    chmod +x yt_dl
    ```

## Usage Workflow

Follow these steps to download and organize your music.

### 1. Add Songs
Edit the `songs.txt` file and add the names of the songs you want to download. Put each song on a new line.

Example `songs.txt`:
```
The Beatles - Hey Jude
Queen - Bohemian Rhapsody
Daft Punk - Get Lucky
```

### 2. Search for URLs
Run the search script to find YouTube URLs for your songs. This script uses the YouTube Data API to fetch the first video result for each song.

```bash
python3 yt_search.py
```
*   **Input**: `songs.txt`
*   **Output**: `results.csv` (contains Song Name and YouTube URL)

### 3. Download Music
Run the download script to download the audio from the URLs found in `results.csv`.

```bash
python3 download_music.py
```
*   **Input**: `results.csv`
*   **Output**: MP3 files saved to your `~/Music` directory (default).

### 4. Rename & Clean Files (Optional)
Run the rename script to clean up filenames (e.g., removing "(Official Video)", "Lyrics", etc.) and format them nicely.

```bash
python3 rename_syntax.py
```
*   **Input**: You will be prompted to enter the directory path containing your music files (e.g., `/Users/yourname/Music`).
*   **Action**: Renames files based on their metadata and cleans up noise in the filenames.

## Files Description

*   `yt_search.py`: Searches YouTube for songs listed in `songs.txt` and saves URLs to `results.csv`.
*   `download_music.py`: Downloads audio from URLs in `results.csv` using the local `yt_dl` binary.
*   `rename_syntax.py`: Renames and organizes music files by cleaning up tags and filenames.
*   `yt_dl`: A standalone executable used by `download_music.py` to handle the actual downloading.
*   `songs.txt`: Input file for song queries.
*   `results.csv`: Intermediate file storing found URLs.
