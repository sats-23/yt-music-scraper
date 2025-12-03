import requests
import csv

API_KEY = "YOUR_YOUTUBE_API_KEY"
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

INPUT_FILE = "songs.txt"
OUTPUT_FILE = "results.csv"


def youtube_search(query):
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": 1,
        "type": "video",
        "key": API_KEY
    }
    response = requests.get(SEARCH_URL, params=params).json()

    if "items" in response and response["items"]:
        vid = response["items"][0]["id"]["videoId"]
        return f"https://www.youtube.com/watch?v={vid}"
    return None


def main():
    print("Reading songs...\n")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        songs = [line.strip() for line in f if line.strip()]

    results = []

    for s in songs:
        url = youtube_search(s)
        print(s, "->", url)
        results.append([s, url])

    print("\nSaving to CSV...")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Song", "YouTube URL"])
        writer.writerows(results)

    print("Done! File saved as:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
