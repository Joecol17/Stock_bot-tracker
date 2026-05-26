"""
headless_launcher.py — Runs the full stock bot stack silently.

Designed to be called by Windows Task Scheduler (on boot / login).
No prompts, no browser windows. Manages three sub-processes:
  1. Cloudflare tunnel (optional — only if cloudflared.exe is present)
  2. Flask dashboard (port 5000)
  3. Auto trader bot

After the bot finishes its daily cycle and enters its long sleep, the launcher
waits for a CTRL+C or the bot process to exit, then optionally shuts down the PC.

Usage:
    python headless_launcher.py
    python headless_launcher.py --no-tunnel
    python headless_launcher.py --shutdown   # override BOT_AUTO_SHUTDOWN from .env
"""

import os
import sys
import time
import signal
import logging
import subprocess
import threading
from dotenv import load_dotenv

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────

LOG_FILE = os.path.join(os.path.dirname(__file__), "launcher.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CF_EXE      = os.path.join(BASE_DIR, "cloudflared.exe")
PYTHON      = sys.executable
AUTO_SHUTDOWN = "--shutdown" in sys.argv or os.getenv("BOT_AUTO_SHUTDOWN", "false").lower() == "true"
NO_TUNNEL   = "--no-tunnel" in sys.argv


# ── Helpers ────────────────────────────────────────────────────────────────

def script(name: str) -> str:
    return os.path.join(BASE_DIR, name)


def start_bg(label: str, *cmd, delay: float = 0) -> subprocess.Popen:
    """Start a background process. Returns the Popen handle."""
    if delay:
        time.sleep(delay)
    logger.info(f"Starting {label}…")
    p = subprocess.Popen(
        list(cmd),
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info(f"{label} started (pid {p.pid})")
    return p


def install_deps():
    req = os.path.join(BASE_DIR, "requirements.txt")
    if not os.path.exists(req):
        return
    logger.info("Installing / verifying Python dependencies…")
    subprocess.run(
        [PYTHON, "-m", "pip", "install", "-r", req, "--quiet"],
        check=False,
    )


def ensure_ollama():
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
        if result.returncode != 0:
            logger.info("Ollama not running — starting ollama serve…")
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(4)
        else:
            logger.info("Ollama already running")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("Ollama not found on PATH — AI decisions may fail")


def shutdown_pc(delay_seconds: int = 120):
    logger.info(f"Auto-shutdown: PC will power off in {delay_seconds}s")
    logger.info("  (Run 'shutdown /a' in cmd to cancel)")
    os.system(f"shutdown /s /t {delay_seconds}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  Stock Bot — Headless Launcher")
    logger.info(f"  Auto-shutdown: {'YES' if AUTO_SHUTDOWN else 'NO'}")
    logger.info(f"  Tunnel:        {'NO (--no-tunnel)' if NO_TUNNEL else 'YES (if cloudflared present)'}")
    logger.info("=" * 60)

    procs: list[subprocess.Popen] = []

    def cleanup(*_):
        logger.info("Shutting down sub-processes…")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # 1. Dependencies
    install_deps()

    # 2. Ollama
    ensure_ollama()

    # 3. Cloudflare tunnel (background — non-blocking)
    if not NO_TUNNEL and os.path.exists(CF_EXE):
        p_tunnel = subprocess.Popen(
            [PYTHON, script("tunnel_helper.py")],
            cwd=BASE_DIR,
        )
        procs.append(p_tunnel)
        time.sleep(8)   # let tunnel establish before dashboard starts
    else:
        if not NO_TUNNEL:
            logger.info("cloudflared.exe not found — remote tunnel disabled")
            logger.info("Run setup_remote.bat to enable remote dashboard access")

    # 4. Dashboard
    p_dash = start_bg("Dashboard", PYTHON, script("dashboard.py"), delay=0)
    procs.append(p_dash)
    time.sleep(3)

    # 5. Bot
    logger.info("Starting trading bot…")
    p_bot = subprocess.Popen(
        [PYTHON, script("auto_trader.py")],
        cwd=BASE_DIR,
    )
    procs.append(p_bot)

    logger.info("All processes started — waiting for bot to finish")
    logger.info("Press Ctrl+C to stop everything")

    try:
        p_bot.wait()
    except KeyboardInterrupt:
        pass

    logger.info("Bot process ended")
    cleanup()

    # Auto-shutdown
    if AUTO_SHUTDOWN:
        shutdown_pc(delay_seconds=120)
    else:
        logger.info("Launcher done — PC will remain on (BOT_AUTO_SHUTDOWN=false)")


if __name__ == "__main__":
    main()
