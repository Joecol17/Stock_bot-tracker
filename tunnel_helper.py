"""
tunnel_helper.py — Starts cloudflared and captures the public tunnel URL.

Supports two modes:
  1. Named Tunnel (permanent URL):
       If tunnel_config.yml exists in the project folder, runs cloudflared
       with that config.  The permanent URL is read immediately from the
       "# public_url: ..." comment in that file and written to tunnel_url.txt
       without waiting — so the dashboard sidebar shows it straight away.

  2. Quick Tunnel (temporary URL, fallback):
       If no config file is found, falls back to a one-off trycloudflare.com
       URL.  URL changes on every restart.
       Run setup_named_tunnel.bat once to switch to a permanent URL.

Run automatically by headless_launcher.py when cloudflared.exe is present.

Usage:
    python tunnel_helper.py [port]
"""

import os
import re
import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [tunnel] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CF_EXE      = os.path.join(BASE_DIR, "cloudflared.exe")
URL_FILE    = os.path.join(BASE_DIR, "tunnel_url.txt")
CONFIG_FILE = os.path.join(BASE_DIR, "tunnel_config.yml")


def clear_url() -> None:
    """Remove stale URL file from last session."""
    try:
        os.remove(URL_FILE)
    except FileNotFoundError:
        pass


def _read_named_url() -> str | None:
    """
    Read the permanent public URL from tunnel_config.yml.
    Looks for a line like:   # public_url: https://dashboard.example.com
    """
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("# public_url:"):
                    url = stripped.split(":", 1)[1].strip()
                    if url.startswith("http"):
                        return url
    except Exception:
        pass
    return None


def start_tunnel(local_port: int = 5000) -> None:
    if not os.path.exists(CF_EXE):
        logger.error("cloudflared.exe not found — run setup_remote.bat first")
        return

    # ── Named Tunnel mode (permanent URL) ─────────────────────────────────
    if os.path.exists(CONFIG_FILE):
        named_url = _read_named_url()
        if named_url:
            # Write URL immediately — it's permanent, no need to wait
            with open(URL_FILE, "w") as f:
                f.write(named_url)
            logger.info("=== NAMED TUNNEL (permanent URL) ===")
            logger.info(f"    {named_url}")
            logger.info("    Bookmark this — it never changes!")
        else:
            logger.warning(
                "tunnel_config.yml found but missing '# public_url:' line. "
                "Re-run setup_named_tunnel.bat to regenerate."
            )

        cmd = [CF_EXE, "tunnel", "--config", CONFIG_FILE, "run"]
        logger.info(f"Starting named tunnel: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )

        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    logger.info(line)
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        finally:
            # Don't clear URL for named tunnels — it's permanent
            logger.info("Named tunnel process exited")
        return

    # ── Quick Tunnel mode (temporary, fallback) ───────────────────────────
    clear_url()
    logger.info("No tunnel_config.yml found — using temporary quick tunnel.")
    logger.info("Run setup_named_tunnel.bat once for a permanent URL.")

    cmd = [CF_EXE, "tunnel", "--url", f"http://localhost:{local_port}"]
    logger.info(f"Starting quick tunnel → http://localhost:{local_port}")

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

            match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if match and not url_found:
                url = match.group(0)
                url_found = True
                with open(URL_FILE, "w") as f:
                    f.write(url)
                logger.info("=== QUICK TUNNEL READY ===")
                logger.info(f"    URL: {url}")
                logger.info("    NOTE: This URL changes on every restart.")
                logger.info("    Run setup_named_tunnel.bat for a permanent URL.")

        proc.wait()

    except KeyboardInterrupt:
        proc.terminate()
    finally:
        clear_url()
        logger.info("Quick tunnel closed")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    start_tunnel(port)
