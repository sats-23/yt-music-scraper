#!/usr/bin/env python3
"""
Local web UI for the YouTube music pipeline.

Run from the project root:
    python3 server.py
and open http://localhost:8000

Directory layout:
    server.py          this file
    index.html         web UI
    yt-dlp             yt-dlp binary
    pipeline/          pipeline stages (imported, not spawned)
      search.py        search_all(songs)        -> [(song, url)]
      download.py      download_all(rows)       -> [(song, ok, msg)]
      rename.py        rename_music_files(dir)  -> [(file, status, detail)]

Stages:  search -> download -> rename
Data flows between stages as Python objects; nothing is written to disk except the MP3s.
"""
import json
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

from pipeline import download_all, rename_music_files, search_all  # noqa: E402
from pipeline.common import MUSIC_DIR as MUSIC  # noqa: E402

PORT = int(os.environ.get("PORT", 8000))
LOCK = threading.RLock()

STAGES = [
    ("search", "Find on YouTube", "Looking up a video for each song"),
    ("download", "Download audio", "Fetching and converting tracks to MP3"),
    ("rename", "Clean up names", "Tidying filenames from the ID3 tags"),
]


def fresh():
    return {
        "state": "idle",  # idle | running | done | error | cancelled
        "stages": [
            {"id": i, "label": l, "desc": d, "status": "pending", "done": 0, "total": 0}
            for i, l, d in STAGES
        ],
        "songs": [],
        "logs": [],
        "files": [],
        "active": [],
        "error": None,
        "started": None,
        "ended": None,
    }


S = fresh()
CANCEL = threading.Event()


class Fail(Exception):
    pass


def log(stage, line):
    with LOCK:
        S["logs"].append({"t": round(time.time() - S["started"], 1), "stage": stage, "line": line})
        del S["logs"][:-400]


def pipeline(songs):
    st = S["stages"]
    cur = 0
    try:
        # 1. Search
        st[0].update(status="running", total=len(songs))

        def on_search(song, url):
            log("search", f"{song} -> {url}")
            with LOCK:
                for s in S["songs"]:
                    if s["name"] == song and s["search"] == "queued":
                        s["search"] = "found" if url else "missing"
                        s["found"] = bool(url)
                        break
                st[0]["done"] += 1

        results = search_all(songs, on_result=on_search, cancel=CANCEL)
        if CANCEL.is_set():
            return
        st[0]["status"] = "done"

        targets = [(song, url) for song, url in results if url]
        if not targets:
            raise Fail("No YouTube results were found for any song.")

        # 2. Download
        cur = 1
        with LOCK:
            st[1].update(status="running", total=len(targets))
            for s in S["songs"]:
                s["download"] = "queued" if s["found"] else "skipped"

        def set_download(song, status):
            for s in S["songs"]:
                if s["name"] == song and s["found"] and s["download"] in ("queued", "running"):
                    s["download"] = status
                    break

        def on_start(song):
            log("download", f"[STARTING] {song}")
            with LOCK:
                set_download(song, "running")
                S["active"].append(song)

        def on_finish(song, ok, msg):
            log("download", f"[{'FINISHED' if ok else 'ERROR'}] {song}" + ("" if ok else f": {msg}"))
            with LOCK:
                set_download(song, "done" if ok else "failed")
                if song in S["active"]:
                    S["active"].remove(song)
                if ok:
                    st[1]["done"] += 1

        outcome = download_all(targets, on_start=on_start, on_finish=on_finish, cancel=CANCEL)
        if CANCEL.is_set():
            return
        if not any(ok for _, ok, _ in outcome):
            raise Fail("No tracks were downloaded. See the log for the yt-dlp / ffmpeg error.")
        st[1]["status"] = "done"

        # 3. Rename
        cur = 2
        mp3s = [f for f in os.listdir(MUSIC) if f.lower().endswith(".mp3")]
        st[2].update(status="running", total=len(mp3s))

        def on_rename(file, status, detail):
            log("rename", f"{file} [{status}]" + (f" {detail}" if detail else ""))
            with LOCK:
                st[2]["done"] += 1

        rename_music_files(MUSIC, on_result=on_rename)
        if CANCEL.is_set():
            return
        st[2].update(status="done", done=len(mp3s))

        with LOCK:
            S["files"] = sorted(f for f in os.listdir(MUSIC) if f.lower().endswith(".mp3"))
            S["state"] = "done"
    except Exception as e:  # noqa: BLE001
        with LOCK:
            st[cur]["status"] = "error"
            S["error"] = str(e)
            S["state"] = "error"
            log(st[cur]["id"], f"ERROR: {e}")
    finally:
        with LOCK:
            if CANCEL.is_set():
                S["state"] = "cancelled"
                for x in st:
                    if x["status"] == "running":
                        x["status"] = "stopped"
            S["ended"] = time.time()
            S["active"] = []


def snapshot():
    with LOCK:
        end = S["ended"] or time.time()
        out = dict(S, elapsed=round(end - S["started"], 1) if S["started"] else 0)
        return json.loads(json.dumps(out))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(BASE, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            self.send_json(snapshot())
        else:
            self.send_error(404)

    def do_POST(self):
        global S
        n = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(n) or b"{}") if n else {}

        if self.path == "/api/start":
            with LOCK:
                if S["state"] == "running":
                    return self.send_json({"error": "A run is already in progress."}, 409)
            songs = [l.strip() for l in str(data.get("songs", "")).splitlines() if l.strip()]
            if not songs:
                return self.send_json({"error": "Add at least one song name."}, 400)
            with LOCK:
                CANCEL.clear()
                S = fresh()
                S["state"] = "running"
                S["started"] = time.time()
                S["songs"] = [
                    {"name": s, "search": "queued", "found": False, "download": "queued"} for s in songs
                ]
            threading.Thread(target=pipeline, args=(songs,), daemon=True).start()
            return self.send_json({"ok": True})

        if self.path == "/api/cancel":
            CANCEL.set()
            return self.send_json({"ok": True})

        if self.path == "/api/reset":
            with LOCK:
                if S["state"] != "running":
                    S = fresh()
            return self.send_json({"ok": True})

        self.send_error(404)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Music pipeline UI running at {url}  (Ctrl+C to stop)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye!")
