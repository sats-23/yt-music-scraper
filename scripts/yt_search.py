import csv
import subprocess
import concurrent.futures
import os

# Paths are relative to the project root (cwd is always set to root by server.py,
# and __file__-based ROOT is used when the script is run standalone).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(ROOT, "songs.txt")
OUTPUT_FILE = os.path.join(ROOT, "results.csv")
YT_DLP = os.path.join(ROOT, "yt-dlp")


def youtube_search(query):
    # Use the local yt-dlp binary from the project root
    result = subprocess.run(
        [YT_DLP, f"ytsearch:{query}", "--get-url"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def main():
    print("Reading songs...\n")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        songs = [line.strip() for line in f if line.strip()]

    results = []

    print("Searching for URLs in parallel...\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_song = {executor.submit(youtube_search, song): song for song in songs}
        for future in concurrent.futures.as_completed(future_to_song):
            song = future_to_song[future]
            try:
                url = future.result()
                print(song, "->", url)
                results.append([song, url])
            except Exception as exc:
                print(f"{song} generated an exception: {exc}")
                results.append([song, None])

    # Sort results to maintain original order
    results.sort(key=lambda x: songs.index(x[0]))

    print("\nSaving to CSV...")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Song", "YouTube URL"])
        writer.writerows(results)

    print("Done! File saved as:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
