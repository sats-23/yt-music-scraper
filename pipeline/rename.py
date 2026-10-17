from __future__ import annotations

import os
import re
import unicodedata
from mutagen import File
from mutagen.easyid3 import EasyID3

# Patterns to remove YouTube noise (in brackets or at the end of the title)
NOISE_PATTERNS = [
    # In brackets: (Official Video), [Official Audio], (4K 60FPS), [Visualizer], (MV), etc.
    r"[\(\[\{]\s*(?:official\s+)?(?:music\s+)?(?:video|audio|visualizer|visualiser|lyric|lyrics?|mv|m/v|hd|hq|4k|1080p|remaster(?:ed)?|stream)(?:[^\)\]\}]*)\s*[\)\]\}]",
    r"[\(\[\{]\s*official\s*[\)\]\}]",
    # Trailing pipe/slash noise: "| Official Music Video", "// Official Audio", etc.
    r"\s*(?:\||\/\/|//)\s*(?:official\s+)?(?:music\s+)?(?:video|audio|visualizer|visualiser|lyrics?|mv).*$",
]

# Delimiters commonly used between artist and title
SPLIT_DELIMITERS = re.compile(r"\s+[-–—|~•]\s+")


def clean_title_noise(text: str) -> str:
    """Remove video junk like (Official Video), [Lyrics], 4K, trailing pipes, etc."""
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    # Remove dangling empty bracket pairs left behind
    text = re.sub(r"[\(\[\{]\s*[\)\]\}]", "", text)
    # Strip any trailing hyphens/pipes/dots left at the end
    text = re.sub(r"[\s\-–—|~•]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_string(s: str) -> str:
    """Normalize string for robust comparison (unicode decomposition, lowercase, no punctuation)."""
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s]", "", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    # Strip common leading article 'the '
    if s.startswith("the "):
        s = s[4:].strip()
    return s


def extract_artist_and_song(title: str, artist: str | None = None) -> tuple[str, str]:
    """Extract clean (artist, song) from metadata title and artist tags.

    Handles cases where title contains 'Artist - Song' or 'Song - Artist',
    avoiding accidental substring truncations.
    """
    clean_title = clean_title_noise(title)
    artist_val = clean_title_noise(artist) if artist else ""

    norm_artist = normalize_string(artist_val) if artist_val else ""
    parts = SPLIT_DELIMITERS.split(clean_title, maxsplit=1)

    if len(parts) == 2:
        left, right = parts[0].strip(), parts[1].strip()
        norm_left = normalize_string(left)
        norm_right = normalize_string(right)

        if norm_artist:
            # Title is 'Artist - Song'
            if norm_left == norm_artist:
                return artist_val or left, right
            # Title is 'Song - Artist'
            if norm_right == norm_artist:
                return artist_val or right, left
        else:
            # No artist tag provided; infer artist and song from split
            return left, right

    # If title didn't split or couldn't match artist, return what we have
    return artist_val, clean_title


def sanitize_filename_part(s: str, max_len: int = 100) -> str:
    """Remove invalid filesystem characters, control chars, and enforce length limits."""
    # Remove illegal characters across Windows/macOS/Linux
    s = re.sub(r'[\\/*?:"<>|]', "", s)
    # Keep printable characters only
    s = "".join(c for c in s if c.isprintable())
    # Remove leading/trailing spaces and dots (invalid on Windows)
    s = s.strip(". ")
    s = re.sub(r"\s+", " ", s)
    return s[:max_len].strip()


def get_unique_path(directory: str, filename: str, original_path: str) -> str:
    """Generate a collision-free target path to prevent data loss or silent overwriting."""
    base, ext = os.path.splitext(filename)
    target_path = os.path.join(directory, filename)
    counter = 1

    orig_abs = os.path.abspath(original_path)
    while os.path.exists(target_path) and os.path.abspath(target_path) != orig_abs:
        target_path = os.path.join(directory, f"{base} ({counter}){ext}")
        counter += 1

    return target_path


def rename_music_files(directory, on_result=None):
    """Rename every .mp3 in `directory` to 'Artist - Title.mp3' using ID3 tags.

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

    if not os.path.isdir(directory):
        return results

    for file in sorted(os.listdir(directory)):
        if not file.lower().endswith(".mp3"):
            continue

        file_path = os.path.join(directory, file)
        if not os.path.isfile(file_path):
            continue

        title = None
        artist = None

        try:
            tags = EasyID3(file_path)
            title = tags.get("title", [None])[0]
            artist = tags.get("artist", [None])[0]
        except Exception:
            try:
                audio = File(file_path, easy=True)
                if audio:
                    title = audio.get("title", [None])[0]
                    artist = audio.get("artist", [None])[0]
            except Exception:
                pass

        # Fallback to filename stem if title tag is completely missing
        if not title or not str(title).strip():
            stem, _ = os.path.splitext(file)
            title = stem

        title_str = str(title).strip()
        artist_str = str(artist).strip() if artist else ""

        final_artist, final_song = extract_artist_and_song(title_str, artist_str)

        song_clean = sanitize_filename_part(final_song) or "Unknown Title"
        artist_clean = sanitize_filename_part(final_artist)

        if artist_clean and artist_clean.lower() != "unknown artist":
            new_name = f"{artist_clean} - {song_clean}.mp3"
        else:
            new_name = f"{song_clean}.mp3"

        new_path = get_unique_path(directory, new_name, file_path)
        final_filename = os.path.basename(new_path)

        if os.path.abspath(new_path) == os.path.abspath(file_path):
            report(file, "unchanged")
            continue

        try:
            os.rename(file_path, new_path)
            report(file, "renamed", final_filename)
        except OSError as e:
            report(file, "error", str(e))

    return results
