"""
wol_relay/app.py — Wake-on-LAN relay service.

Deploy this to Render.com (free tier) once.
Set these environment variables in Render dashboard:
  PC_MAC       = BC-F4-D4-A9-18-D1     ← your PC's MAC
  ROUTER_IP    = <your home external IP OR leave blank for 255.255.255.255>
  WOL_PORT     = 9                       ← default, matches your port-forward rule
  WAKE_SECRET  = <random string>         ← paste into docs/config.js as WAKE_TOKEN

Then set docs/config.js:
  window.WAKE_RELAY_URL = "https://your-app-name.onrender.com";
  window.WAKE_TOKEN     = "<same random string>";
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import wakeonlan

app = Flask(__name__)

# Allow the GitHub Pages site (and localhost for dev) to call this
CORS(app, origins=[
    "https://joecol17.github.io",
    "http://localhost:*",
    "http://127.0.0.1:*",
])

PC_MAC      = os.environ.get("PC_MAC",      "BC-F4-D4-A9-18-D1")
ROUTER_IP   = os.environ.get("ROUTER_IP",   "255.255.255.255")
WOL_PORT    = int(os.environ.get("WOL_PORT", "9"))
WAKE_SECRET = os.environ.get("WAKE_SECRET", "")


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/wake", methods=["POST"])
def wake():
    # Optional token check
    if WAKE_SECRET:
        token = request.headers.get("X-Wake-Token", "")
        if token != WAKE_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    try:
        wakeonlan.send_magic_packet(PC_MAC, ip_address=ROUTER_IP, port=WOL_PORT)
        return jsonify({"ok": True, "message": f"Magic packet sent to {PC_MAC} via {ROUTER_IP}:{WOL_PORT}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
