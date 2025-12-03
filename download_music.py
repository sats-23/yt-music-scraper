import csv
import subprocess
import shlex

CSV_FILE = "results.csv"
YT_DL_CMD = "./yt_dl -x --audio-format mp3 --audio-quality 0 --embed-metadata -o '~/Music/%(title)s.%(ext)s'"

def main():
    urls = []

    # Read URLs from CSV
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("YouTube URL")
            if url:
                urls.append(url.strip())

    print(f"Found {len(urls)} URLs to download.")
    print("----------------------------------")

    # Loop through and run yt_dl
    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] Downloading: {url}")

        cmd = f"{YT_DL_CMD} {url}"

        # Use subprocess to run the command
        process = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            print("✓ Downloaded successfully\n")
        else:
            print("✗ Failed download\n")
            print(stderr.decode())

    print("All downloads finished.")

if __name__ == "__main__":
    main()
