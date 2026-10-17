import os
import re
from mutagen.easyid3 import EasyID3

# Patterns to remove as noise (inside brackets)
REMOVE_PATTERNS = [
    r"\(official.+?\)",          # (Official...)
    r"\[official.+?\]",          # [Official...]
    r"\(music.+?\)",             # (Music Video / Music)
    r"\(lyrics?.*?\)",           # (Lyric / Lyrics)
    r"\(audio?.*?\)",            # (Audio)
    r"\(video.*?\)",             # (Video)
    r"\(mv.*?\)",                # (MV)
    r"\(hd.*?\)",                # (HD)
    r"\(hq.*?\)",                # (HQ)
]

def clean_brackets(text: str) -> str:
    """Remove junk in brackets like (Official Video), (Lyrics), etc."""
    for p in REMOVE_PATTERNS:
        text = re.sub(p, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def normalize(s: str) -> str:
    """Normalize for loose comparisons."""
    return re.sub(r"\s+", " ", s.lower()).strip()

def strip_artist_from_title(title: str, artist: str) -> str:
    """
    If title looks like 'Artist - Song', and artist matches the left side,
    return just 'Song'. Otherwise return title.
    """
    t_norm = clean_brackets(title)
    a_norm = normalize(artist)

    # Try to split "Artist - Song"
    if " - " in t_norm:
        left, right = t_norm.split(" - ", 1)
        left_norm = normalize(left)

        # If the left side is (roughly) the artist, use right part as song
        if a_norm in left_norm or left_norm in a_norm:
            return right.strip()

    # Fallback: just return cleaned title
    return t_norm

def sanitize_filename_part(s: str) -> str:
    """Remove characters that are invalid in filenames on most OSes."""
    s = re.sub(r'[\\/*?:"<>|]', "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def rename_music_files(directory, on_result=None):
    """Rename every .mp3 in `directory` to 'Song - Artist.mp3' using its ID3 tags.

    Returns [(old_name, status, detail), ...] where status is one of
    'renamed', 'unchanged', 'skipped', 'error'.
    `on_result(old_name, status, detail)` is called per file.
    """
    directory = os.path.expanduser(directory)
    results = []

    def report(file, status, detail=""):
        results.append((file, status, detail))
        if on_result:
            on_result(file, status, detail)

    for file in os.listdir(directory):
        if not file.lower().endswith(".mp3"):
            continue

        file_path = os.path.join(directory, file)

        try:
            tags = EasyID3(file_path)
        except Exception:
            report(file, "skipped", "no ID3 tags")
            continue

        title = tags.get("title", [None])[0]
        artist = tags.get("artist", [None])[0]

        if not title or not artist:
            report(file, "skipped", "missing title/artist")
            continue

        # Get clean song name from title
        song = strip_artist_from_title(title, artist)

        # Final safety cleanup
        song_clean = sanitize_filename_part(song)
        artist_clean = sanitize_filename_part(artist)

        new_name = f"{song_clean} - {artist_clean}.mp3"
        new_path = os.path.join(directory, new_name)

        if new_path == file_path:
            report(file, "unchanged")
            continue

        try:
            os.rename(file_path, new_path)
            report(file, "renamed", new_name)
        except Exception as e:
            report(file, "error", str(e))

    return results
