"""MiniCrew desktop — a native window wrapping the Streamlit literature app.

Starts Streamlit headless on a local port, waits until it's healthy, then opens a
pywebview window pointing at it. Closing the window stops the server. Run the
whole stack (including the Mongo+Qdrant containers) on a machine WITH a display.

    scripts/minicrew-desktop

Set MINICREW_DESKTOP_NOWINDOW=1 to exercise the launch/health logic with no GUI
(useful on a headless box).
"""
import atexit
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))    # minicrew/
APP = os.path.join(HERE, "app", "Home.py")
VENV_STREAMLIT = os.path.join(HERE, ".venv", "bin", "streamlit")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_health(url, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    port = _free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = (os.path.join(HERE, "src") + os.pathsep
                         + env.get("PYTHONPATH", ""))
    streamlit = VENV_STREAMLIT if os.path.exists(VENV_STREAMLIT) else "streamlit"
    # own session/group so we can reap streamlit AND its server child cleanly;
    # logs to a file (not the terminal) so the desktop launch stays quiet.
    log = open(os.path.join(HERE, ".streamlit-desktop.log"), "w")
    proc = subprocess.Popen(
        [streamlit, "run", APP,
         "--server.headless", "true",
         "--server.address", "127.0.0.1",
         "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

    def _stop():
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()
    atexit.register(_stop)

    url = f"http://127.0.0.1:{port}"
    print(f"starting MiniCrew at {url} …")
    if not _wait_health(url + "/_stcore/health", timeout=90):
        print(f"error: Streamlit did not start — see {log.name}", file=sys.stderr)
        _stop()
        return 1

    if os.environ.get("MINICREW_DESKTOP_NOWINDOW"):
        print(f"[NOWINDOW] server healthy at {url}; skipping GUI window.")
        _stop()
        return 0

    import webview
    webview.create_window("MiniCrew · Literature", url,
                          width=1320, height=900, min_size=(900, 600))
    try:
        webview.start()           # blocks until the window is closed
    finally:
        _stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
