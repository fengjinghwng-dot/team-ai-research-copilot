"""Run the web UI and private API under one Render service, including graceful shutdown."""
import os
import signal
import subprocess
import sys
import time
import urllib.request

children = []
stopping = False


def shutdown(*_):
    global stopping
    stopping = True
    for child in children:
        if child.poll() is None:
            child.terminate()


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


def main():
    subprocess.run([sys.executable, "-m", "copilot.cli", "migrate"], check=True)
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "copilot.api:app",
                            "--host", "127.0.0.1", "--port", "8000", "--root-path", "/api"])
    children.append(api)
    for _ in range(60):
        if stopping or api.poll() is not None:
            return 1
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/readyz", timeout=2) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(.5)
    else:
        raise RuntimeError("API failed its database readiness check")
    env = {**os.environ, "HOSTNAME": "0.0.0.0", "PORT": os.environ.get("PORT", "10000")}
    children.append(subprocess.Popen(["node", "web/server.js"], env=env))
    while not stopping:
        if any(child.poll() is not None for child in children):
            return 1
        time.sleep(.5)
    return 0


if __name__ == "__main__":
    try:
        result = main()
    finally:
        shutdown()
        for process in children:
            try:
                process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                process.kill()
    sys.exit(result)
