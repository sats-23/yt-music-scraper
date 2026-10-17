import concurrent.futures

from .common import YT_DLP, run


def youtube_search(query, cancel=None):
    """Return the first YouTube URL for `query`, or None."""
    result = run(
        [
            YT_DLP,
            f"ytsearch1:{query}",
            "--print", "%(webpage_url)s",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
        ],
        cancel=cancel,
    )
    if result.returncode == 0:
        urls = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return urls[0] if urls else None
    return None


def search_all(songs, on_result=None, cancel=None):
    """Search every song in parallel.

    Returns [(song, url_or_None), ...] in input order.
    `on_result(song, url)` is called as each search finishes.
    """
    results = [(s, None) for s in songs]

    def work(i):
        try:
            url = youtube_search(songs[i], cancel)
        except Exception:  # noqa: BLE001
            url = None
        results[i] = (songs[i], url)
        if on_result:
            on_result(songs[i], url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(work, range(len(songs))))
    return results
