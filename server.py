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
    scripts/           pipeline scripts
      yt_search.py
      download_music.py
      rename_syntax.py
      init_files.py    first-time setup helper

Stages:  save songs.txt -> scripts/yt_search.py -> scripts/download_music.py -> scripts/rename_syntax.py
The scripts are not modified; they run as subprocesses with cwd set to the project root.
"""
import csv
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

# Bootstrap: create songs.txt, results.csv, Music/ if they don't exist yet.
_spec = importlib.util.spec_from_file_location(
    "init_files", os.path.join(BASE, "scripts", "init_files.py")
)
_init = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_init)
_init.ensure(verbose=True)
PORT = int(os.environ.get("PORT", 8000))
MUSIC = os.path.join(BASE, "Music")  # download_music.py writes to ./Music
SCRIPTS = [
    os.path.join("scripts", "yt_search.py"),
    os.path.join("scripts", "download_music.py"),
    os.path.join("scripts", "rename_syntax.py"),
]
LOCK = threading.RLock()

STAGES = [
    ("save", "Save songs", "Writing your list to songs.txt"),
    ("search", "Find on YouTube", "yt_search.py is looking up a video for each song"),
    ("download", "Download audio", "download_music.py is fetching and converting tracks to MP3"),
    ("rename", "Clean up names", "rename_syntax.py is tidying filenames from the ID3 tags"),
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
PROC = None
CANCEL = False
DL_START = 0.0
STARTING = set()


class Fail(Exception):
    pass


def clean_name(song):
    # Same rule download_music.py uses for its output filenames
    return "".join(c for c in song if c.isalnum() or c in (" ", "-", "_")).strip()


def log(stage, line):
    with LOCK:
        S["logs"].append({"t": round(time.time() - S["started"], 1), "stage": stage, "line": line})
        del S["logs"][:-400]


def run_script(script, on_line, stdin_text=None):
    global PROC
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    p = subprocess.Popen(
        [sys.executable, "-u", script],
        cwd=BASE,
        env=env,
        stdin=subprocess.PIPE if stdin_text else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    PROC = p
    if stdin_text:
        p.stdin.write(stdin_text)
        p.stdin.close()
    for line in p.stdout:
        line = line.rstrip()
        if line:
            on_line(line)
    return p.wait()


def compute_downloads(final=False):
    """Derive per-song download status from files appearing in Music/."""
    with LOCK:
        done = 0
        active = []
        for s in S["songs"]:
            if not s["found"]:
                continue
            path = os.path.join(MUSIC, clean_name(s["name"]) + ".mp3")
            if os.path.exists(path) and os.path.getmtime(path) >= DL_START:
                s["download"] = "done"
                done += 1
            elif final:
                s["download"] = "failed"
            elif s["name"] in STARTING:
                s["download"] = "running"
                active.append(s["name"])
            else:
                s["download"] = "queued"
        S["stages"][2]["done"] = done
        S["active"] = active
        return done


def pipeline(songs):
    global DL_START
    st = S["stages"]
    cur = 0
    try:
        # 1. Save
        st[0]["status"] = "running"
        with open(os.path.join(BASE, "songs.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(songs) + "\n")
        st[0].update(status="done", done=len(songs), total=len(songs))
        log("save", f"Saved {len(songs)} songs to songs.txt")

        # 2. Search
        cur = 1
        st[1].update(status="running", total=len(songs))

        def on_search(line):
            log("search", line)
            if " -> " in line:
                name, _, val = line.rpartition(" -> ")
                with LOCK:
                    for s in S["songs"]:
                        if s["name"] == name and s["search"] == "queued":
                            s["search"] = "missing" if val.strip() in ("None", "") else "found"
                            st[1]["done"] += 1
                            break

        if run_script(os.path.join("scripts", "yt_search.py"), on_search) != 0 and not CANCEL:
            raise Fail("scripts/yt_search.py exited with an error. Check the log and that ./yt-dlp is executable.")
        if CANCEL:
            return

        with LOCK:  # trust results.csv as the final word on what was found
            try:
                with open(os.path.join(BASE, "results.csv"), encoding="utf-8") as f:
                    found = {r["Song"] for r in csv.DictReader(f) if (r.get("YouTube URL") or "").strip()}
                for s in S["songs"]:
                    s["found"] = s["name"] in found
                    s["search"] = "found" if s["found"] else "missing"
            except OSError:
                raise Fail("results.csv was not created.")
            st[1].update(status="done", done=len(songs))
        targets = [s for s in S["songs"] if s["found"]]
        if not targets:
            raise Fail("No YouTube results were found for any song.")

        # 3. Download
        cur = 2
        DL_START = time.time() - 1
        STARTING.clear()
        with LOCK:
            st[2].update(status="running", total=len(targets))
            for s in S["songs"]:
                s["download"] = "queued" if s["found"] else "skipped"

        def on_dl(line):
            log("download", line)
            if line.startswith("[STARTING] "):
                STARTING.add(line[len("[STARTING] "):].strip())

        rc = run_script(os.path.join("scripts", "download_music.py"), on_dl)
        if CANCEL:
            return
        n = compute_downloads(final=True)
        if rc != 0 or n == 0:
            raise Fail("No tracks were downloaded. See the log for the yt-dlp / ffmpeg error.")
        st[2]["status"] = "done"

        # 4. Rename (script asks for a directory on stdin)
        cur = 3
        mp3s = [f for f in os.listdir(MUSIC) if f.lower().endswith(".mp3")]
        st[3].update(status="running", total=len(mp3s))

        def on_rename(line):
            log("rename", line)
            if line.startswith(("✔", "⚠", "❌")):
                with LOCK:
                    st[3]["done"] += 1

        if run_script(os.path.join("scripts", "rename_syntax.py"), on_rename, stdin_text=MUSIC + "\n") != 0 and not CANCEL:
            raise Fail("scripts/rename_syntax.py exited with an error.")
        if CANCEL:
            return
        st[3].update(status="done", done=len(mp3s))

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
            if CANCEL:
                S["state"] = "cancelled"
                for x in st:
                    if x["status"] == "running":
                        x["status"] = "stopped"
            S["ended"] = time.time()
            S["active"] = []


def snapshot():
    with LOCK:
        if S["stages"][2]["status"] == "running":
            compute_downloads()
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
        elif self.path == "/api/songs":
            try:
                with open(os.path.join(BASE, "songs.txt"), encoding="utf-8") as f:
                    self.send_json({"text": f.read()})
            except OSError:
                self.send_json({"text": ""})
        else:
            self.send_error(404)

    def do_POST(self):
        global S, CANCEL
        n = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(n) or b"{}") if n else {}

        if self.path == "/api/start":
            with LOCK:
                if S["state"] == "running":
                    return self.send_json({"error": "A run is already in progress."}, 409)
            missing = [s for s in SCRIPTS if not os.path.exists(os.path.join(BASE, s))]
            if missing:
                return self.send_json({"error": "Missing scripts: " + ", ".join(missing)}, 400)
            songs = [l.strip() for l in str(data.get("songs", "")).splitlines() if l.strip()]
            if not songs:
                return self.send_json({"error": "Add at least one song name."}, 400)
            with LOCK:
                CANCEL = False
                S = fresh()
                S["state"] = "running"
                S["started"] = time.time()
                S["songs"] = [
                    {"name": s, "search": "queued", "found": False, "download": "queued"} for s in songs
                ]
            threading.Thread(target=pipeline, args=(songs,), daemon=True).start()
            return self.send_json({"ok": True})

        if self.path == "/api/cancel":
            CANCEL = True
            if PROC and PROC.poll() is None:
                PROC.terminate()
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
