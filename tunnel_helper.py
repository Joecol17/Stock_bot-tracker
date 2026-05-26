"""
tunnel_helper.py — Starts cloudflared and captures the public tunnel URL.

Run automatically by headless_launcher.py when cloudflared.exe is present.
Writes the URL to tunnel_url.txt so the dashboard can serve it via /api/botdata.

Usage:
    python tunnel_helper.py
"""

import os
import re
import subprocess
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [tunnel] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CF_EXE   = os.path.join(BASE_DIR, "cloudflared.exe")
URL_FILE = os.path.join(BASE_DIR, "tunnel_url.txt")


def clear_url():
    """Remove stale URL file from last session."""
    try:
        os.remove(URL_FILE)
    except FileNotFoundError:
        pass


def start_tunnel(local_port: int = 5000) -> None:
    if not os.path.exists(CF_EXE):
        logger.error("cloudflared.exe not found — run setup_remote.bat first")
        return

    clear_url()

    cmd = [CF_EXE, "tunnel", "--url", f"http://localhost:{local_port}"]
    logger.info(f"Starting tunnel → http://localhost:{local_port}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )

    url_found = False
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                logger.info(line)

            # cloudflared prints the URL in a line like:
            # "| https://xxxx.trycloudflare.com                      |"
            match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if match and not url_found:
                url = match.group(0)
                url_found = True
                with open(URL_FILE, "w") as f:
                    f.write(url)
                logger.info(f"=== TUNNEL READY ===")
                logger.info(f"    Dashboard URL: {url}")
                logger.info(f"    Bookmark this on your phone / remote device")

        proc.wait()

    except KeyboardInterrupt:
        proc.terminate()
    finally:
        clear_url()
        logger.info("Tunnel closed")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    start_tunnel(port)
