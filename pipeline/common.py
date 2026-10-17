import os
import shutil
import subprocess
import threading
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YT_DLP = os.path.join(ROOT, "yt-dlp")
MUSIC_DIR = os.path.join(ROOT, "Music")

# Ensure PATH includes standard Homebrew and local binary directories
_path = os.environ.get("PATH", "")
for _p in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]:
    if _p not in _path.split(os.pathsep):
        _path = f"{_p}{os.pathsep}{_path}"
ENV = dict(os.environ, PATH=_path)
FFMPEG_BIN = shutil.which("ffmpeg", path=_path)
if not FFMPEG_BIN:
    # Fall back to the static ffmpeg bundled with the imageio-ffmpeg package
    try:
        import imageio_ffmpeg
        FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass


def run(cmd, cancel: threading.Event = None, timeout=None):
    """Run a command; kill it if `cancel` is set. Raises subprocess.TimeoutExpired on timeout."""
    p = subprocess.Popen(
        cmd, cwd=ROOT, env=ENV, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    waited = 0.0
    while True:
        try:
            out, err = p.communicate(timeout=0.3)
            return SimpleNamespace(returncode=p.returncode, stdout=out, stderr=err)
        except subprocess.TimeoutExpired:
            waited += 0.3
            if (cancel and cancel.is_set()) or (timeout and waited >= timeout):
                p.kill()
                p.communicate()
                if cancel and cancel.is_set():
                    return SimpleNamespace(returncode=-1, stdout="", stderr="cancelled")
                raise subprocess.TimeoutExpired(cmd, timeout)
