from __future__ import annotations

import os
import re
import unicodedata
from mutagen import File
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

# Patterns to remove YouTube noise (in brackets or at the end of the title)
NOISE_PATTERNS = [
    # In brackets: (Official Video), [Official Audio], (4K 60FPS), [Visualizer], (MV), (Soundtrack), etc.
    r"[\(\[\{『]\s*(?:official\s+)?(?:music\s+)?(?:video|audio|visualizer|visualiser|lyric|lyrics?|mv|m/v|hd|hq|4k|1080p|remaster(?:ed)?|stream|paroles\s+audio\s+hq|paroles\s+audio|audio\s+only|lyrics\s+hd|high[- ]quality\s+audio|hq\s+audio|audio\s+hq|video\s+version\s+audio|remastered\s*\/\s*audio|tiktok\s+mashup|tiktok\s+song|lyrics\s+on\s+screen|lyrics\s*\/\s*lyric\s+video|high\s+quality|michael\s+soundtrack|soundtrack)(?:[^\)\]\}』]*)\s*[\)\]\}』]",
    r"[\(\[\{]\s*official\s*[\)\]\}]",
    r"\*OFFICIAL\s+[^\*]+\*",
    r"\"Audio\"",
    # Trailing pipe/slash/etc noise: "| Official Music Video", "// Official Audio", etc.
    r"\s*(?:\||\/\/|//)\s*(?:official\s+)?(?:music\s+)?(?:video|audio|visualizer|visualiser|lyrics?|mv|pop\s+song|mashup\s+by\s+.*|.*lyrics).*$",
    r"\s*\|\s*.*$",
    # Trailing audio / lyrics / official video without brackets at the end
    r"\s+(?:official\s+lyric\s+video|official\s+music\s+video|official\s+audio|official\s+video|lyric\s+video|audio\s+hq|hq\s+audio|audio\s+only|audio|lyrics?)$",
]

# Delimiters: hyphens with whitespace, en/em dashes, tildes, pipes
SPLIT_DELIMITERS = re.compile(r"\s+[-–—‒~|•]\s+|\s+[-–—‒]\s*|\s*[-–—‒]\s+")

KNOWN_ARTISTS = {
    "maroon 5", "portugal the man", "aya nakamura", "charli xcx", "billy davis",
    "saint motel", "drake", "the jacksons", "jacksons", "muki", "michael jackson", "lana del rey",
    "katseye", "katseye 캣츠아이", "luis fonsi", "demi lovato",
    "ariana grande", "tate mcrae", "charlie puth", "dua lipa", "the weeknd", "selena gomez"
}


def clean_title_noise(text: str) -> str:
    """Remove video junk like (Official Video), [Lyrics], 4K, trailing pipes, etc."""
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    # Extra pass for trailing audio/lyrics noise that might have been unbracketed
    text = re.sub(
        r"\s+(?:official\s+lyric\s+video|official\s+music\s+video|official\s+audio|official\s+video|lyric\s+video|audio\s+hq|hq\s+audio|audio\s+only|audio|lyrics?)$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove dangling empty bracket pairs left behind
    text = re.sub(r"[\(\[\{]\s*[\)\]\}]", "", text)
    # Strip any trailing hyphens/pipes/dots left at the end
    text = re.sub(r"[\s\-–—‒|~•.]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_string(s: str) -> str:
    """Normalize string for robust comparison (unicode decomposition, lowercase, no punctuation)."""
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("$", "s")  # handle cases like Pink Sweat$ -> pink sweats
    s = re.sub(r"[^\w\s]", "", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    # Strip common leading article 'the '
    if s.startswith("the "):
        s = s[4:].strip()
    return s


def sanitize_filename_part(s: str, max_len: int = 100) -> str:
    """Remove invalid filesystem characters, control chars, and enforce length limits."""
    s = re.sub(r'[\\/*?:"<>|]', "", s)
    s = "".join(c for c in s if c.isprintable())
    s = s.strip(". ")
    s = re.sub(r"\s+", " ", s)
    return s[:max_len].strip()


def clean_artist_tag(artist: str) -> str:
    """Clean channel metadata from artist tag (Topic channels, VEVO, etc.)."""
    if not artist:
        return ""
    artist = re.sub(r"\s*[-–—‒]\s*Topic\s*$", "", artist, flags=re.IGNORECASE)
    artist = re.sub(r"^@?([a-zA-Z0-9_]+)VEVO$", r"\1", artist, flags=re.IGNORECASE)
    artist = re.sub(r"\s+(?:Official|Audios|Lyrics|Channel|Records|Brazil)$", "", artist, flags=re.IGNORECASE)
    artist = clean_title_noise(artist)
    return artist


def deduplicate_ft(s: str) -> str:
    """Fix strings like 'bloodonmyhands ft. Flo Milli ft. Flo Milli'."""
    pattern = r"(\b(?:ft\.?|feat\.?)\s+[^\(\[\-]+?)(?:\s+\1)+"
    return re.sub(pattern, r"\1", s, flags=re.IGNORECASE)


def strip_outer_quotes(s: str) -> str:
    """Strip bounding quotation marks."""
    return s.strip(" \"'\u201c\u201d\u2018\u2019")


def extract_artist_and_song(title: str, artist: str | None = None) -> tuple[str, str]:
    """Extract clean (artist, song) from metadata title and artist tags.

    Handles cases where title contains 'Artist - Song' or 'Song - Artist',
    quoted song titles, channel names as artist tags, and missing delimiters.
    """
    clean_t = clean_title_noise(title)
    artist_val = clean_artist_tag(artist)

    # 1. Check for quoted song title like: Artist "Song" or Artist 'Song' or Artist “Song”
    quote_match = re.match(r'^(.*?)\s+[“"\'\‘]([^”"\'\’]{2,})[”"\'\’]\s*(.*)$', clean_t)
    if quote_match:
        prefix = quote_match.group(1).strip()
        quoted = quote_match.group(2).strip()
        suffix = quote_match.group(3).strip()
        if prefix and not re.search(r"\s+[-–—‒~|•]\s+", prefix):
            full_song = clean_title_noise(f"{quoted} {suffix}".strip())
            return prefix, full_song

    # 2. Check delimiters (hyphens, dashes, pipes)
    parts = SPLIT_DELIMITERS.split(clean_t, maxsplit=1)
    if len(parts) == 2:
        left, right = strip_outer_quotes(clean_title_noise(parts[0])), strip_outer_quotes(clean_title_noise(parts[1]))
        norm_left = normalize_string(left)
        norm_right = normalize_string(right)
        norm_art = normalize_string(artist_val)

        # Check if right is the artist:
        right_without_parens = re.sub(r"[\(\[\{].*?[\)\]\}]", "", right)
        norm_right_main = normalize_string(right_without_parens)

        if norm_art and (norm_art == norm_right_main or norm_art in norm_right_main) and not (norm_art in norm_left):
            return right, left

        # Check if right is a known artist (for Song - Artist format when artist tag is channel name)
        if norm_right_main in KNOWN_ARTISTS or any(norm_right_main == normalize_string(k) for k in KNOWN_ARTISTS):
            return right, left

        # If left starts or ends with quotes or right looks like artist
        if norm_art and (norm_art in norm_left or norm_left in norm_art):
            return left, right

        # Default for delimiters: Left is Artist, Right is Song
        return left, right

    # 3. Colon delimiter: Artist: Song (if no dash was found)
    colon_match = re.match(r"^([^:]+):\s+(.+)$", clean_t)
    if colon_match:
        left, right = colon_match.group(1).strip(), clean_title_noise(colon_match.group(2))
        return left, right

    # 4. Check if title starts with artist_val (e.g. "Luis Fonsi ft. Demi Lovato Échame La Culpa")
    if artist_val:
        norm_art = normalize_string(artist_val)
        norm_t = normalize_string(clean_t)
        if norm_t.startswith(norm_art) and len(clean_t) > len(artist_val):
            rest = clean_t[len(artist_val):].strip()
            # If rest starts with ft./feat./& e.g. "ft. Demi Lovato Échame La Culpa"
            feat_match = re.match(r"^(?:ft\.?|feat\.?|&|x)\s+([A-Z][a-zA-Z0-9_\.]+(?:\s+[A-Z][a-zA-Z0-9_\.]+)?)\s+(.+)$", rest)
            if feat_match:
                featured_artist = feat_match.group(1).strip()
                song_part = feat_match.group(2).strip()
                if song_part:
                    return f"{artist_val} ft. {featured_artist}", clean_title_noise(song_part)

            song_part = clean_t[len(artist_val):].strip(" -:–—|")
            if song_part:
                return artist_val, clean_title_noise(song_part)

    # 5. Check if clean_t starts with a known artist (e.g. "Michael Jackson Smooth Criminal", "Lana Del Rey-Diet Mountain Dew", "AYA NAKAMURA Djadja")
    for known in sorted(KNOWN_ARTISTS, key=len, reverse=True):
        norm_t = normalize_string(clean_t)
        if norm_t.startswith(known) and len(norm_t) > len(known):
            words_known = known.split()
            words_t = clean_t.replace("-", " ").split()
            if len(words_t) > len(words_known):
                art_part = clean_t[:len(" ".join(words_t[:len(words_known)]))].strip(" -:–—|")
                song_part = clean_t[len(art_part):].strip(" -:–—|")
                return art_part, clean_title_noise(song_part)

    # 6. Fallback: artist_val and clean_t
    return artist_val, clean_t


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

    Also updates ID3 tags so file metadata matches the cleaned artist and title.
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
        final_song = deduplicate_ft(final_song)
        final_song = strip_outer_quotes(final_song)
        final_artist = strip_outer_quotes(final_artist)

        song_clean = sanitize_filename_part(final_song) or "Unknown Title"
        artist_clean = sanitize_filename_part(final_artist)

        if artist_clean and artist_clean.lower() != "unknown artist":
            new_name = f"{artist_clean} - {song_clean}.mp3"
        else:
            new_name = f"{song_clean}.mp3"

        # Update ID3 tags so embedded metadata matches the clean artist and title
        try:
            id3 = EasyID3(file_path)
        except Exception:
            try:
                mp3_obj = MP3(file_path)
                mp3_obj.add_tags()
                mp3_obj.save()
                id3 = EasyID3(file_path)
            except Exception:
                id3 = None

        if id3 is not None:
            try:
                id3["title"] = song_clean
                if artist_clean and artist_clean.lower() != "unknown artist":
                    id3["artist"] = artist_clean
                id3.save(file_path)
            except Exception:
                pass

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
