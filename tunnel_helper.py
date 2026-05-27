"""
tunnel_helper.py — Starts a public tunnel and captures the URL.

Priority order (uses the first one that's configured):
  1. Named Tunnel  — tunnel_config.yml present → cloudflared named tunnel
                     (permanent URL set up via setup_named_tunnel.bat)
  2. ngrok static  — ngrok.exe present + NGROK_STATIC_DOMAIN in .env
                     (free permanent URL, set up via setup_ngrok.bat)
  3. Quick Tunnel  — cloudflared.exe present, no config
                     (temporary trycloudflare.com URL, changes on restart)

Run setup_ngrok.bat (free) or setup_named_tunnel.bat (needs a domain)
once to get a permanent URL.

Usage:
    python tunnel_helper.py [port]
"""

import os
import re
import subprocess
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [tunnel] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CF_EXE      = os.path.join(BASE_DIR, "cloudflared.exe")
NGROK_EXE   = os.path.join(BASE_DIR, "ngrok.exe")
URL_FILE    = os.path.join(BASE_DIR, "tunnel_url.txt")
CONFIG_FILE = os.path.join(BASE_DIR, "tunnel_config.yml")


def clear_url() -> None:
    try:
        os.remove(URL_FILE)
    except FileNotFoundError:
        pass


def write_url(url: str) -> None:
    with open(URL_FILE, "w") as f:
        f.write(url)


def _read_named_url() -> str | None:
    """Read permanent URL from '# public_url:' line in tunnel_config.yml."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("# public_url:"):
                    url = s.split(":", 1)[1].strip()
                    if url.startswith("http"):
                        return url
    except Exception:
        pass
    return None


# ── 1. Named Tunnel (cloudflared + tunnel_config.yml) ─────────────────────────

def _run_named_tunnel() -> None:
    named_url = _read_named_url()
    if named_url:
        write_url(named_url)
        logger.info("=== NAMED TUNNEL (permanent URL) ===")
        logger.info(f"    {named_url}")
        logger.info("    Bookmark this — it never changes!")
    else:
        logger.warning(
            "tunnel_config.yml found but missing '# public_url:' comment. "
            "Re-run setup_named_tunnel.bat to fix."
        )

    cmd = [CF_EXE, "tunnel", "--config", CONFIG_FILE, "run"]
    logger.info(f"Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    try:
        for line in proc.stdout:
            if line.rstrip():
                logger.info(line.rstrip())
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        logger.info("Named tunnel process exited (URL preserved)")


# ── 2. ngrok static domain (free permanent URL) ───────────────────────────────

def _run_ngrok(local_port: int, static_domain: str) -> None:
    public_url = f"https://{static_domain}"
    write_url(public_url)
    logger.info("=== NGROK STATIC DOMAIN (permanent URL) ===")
    logger.info(f"    {public_url}")
    logger.info("    Bookmark this — it never changes!")

    cmd = [NGROK_EXE, "http",
           f"--domain={static_domain}",
           "--log=stdout",
           f"localhost:{local_port}"]
    logger.info(f"Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    try:
        for line in proc.stdout:
            if line.rstrip():
                logger.info(line.rstrip())
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        logger.info("ngrok process exited (URL preserved)")


# ── 3. Quick Tunnel (cloudflared temporary, fallback) ─────────────────────────

def _run_quick_tunnel(local_port: int) -> None:
    clear_url()
    logger.info("No permanent tunnel configured — using temporary quick tunnel.")
    logger.info("Run setup_ngrok.bat (free) for a permanent URL.")

    cmd = [CF_EXE, "tunnel", "--url", f"http://localhost:{local_port}"]
    logger.info(f"Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    url_found = False
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                logger.info(line)
            match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if match and not url_found:
                url_found = True
                url = match.group(0)
                write_url(url)
                logger.info("=== QUICK TUNNEL READY ===")
                logger.info(f"    URL: {url}")
                logger.info("    NOTE: URL changes every restart. Run setup_ngrok.bat for a free permanent URL.")
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        clear_url()
        logger.info("Quick tunnel closed")


# ── Entry point ───────────────────────────────────────────────────────────────

def start_tunnel(local_port: int = 5000) -> None:
    # Priority 1: cloudflared named tunnel
    if os.path.exists(CONFIG_FILE):
        if not os.path.exists(CF_EXE):
            logger.error("tunnel_config.yml found but cloudflared.exe is missing.")
            return
        _run_named_tunnel()
        return

    # Priority 2: ngrok with static domain
    ngrok_domain = os.getenv("NGROK_STATIC_DOMAIN", "").strip()
    if os.path.exists(NGROK_EXE) and ngrok_domain:
        _run_ngrok(local_port, ngrok_domain)
        return

    # Priority 3: cloudflared quick tunnel (temporary fallback)
    if os.path.exists(CF_EXE):
        _run_quick_tunnel(local_port)
        return

    logger.error(
        "No tunnel tool found. Run setup_ngrok.bat (free) or setup_remote.bat."
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    start_tunnel(port)
