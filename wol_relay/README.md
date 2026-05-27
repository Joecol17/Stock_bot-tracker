# WoL Relay — Deploy to Render.com (free)

This tiny service sends a Wake-on-LAN magic packet over the internet to your home PC.
It lives in the cloud 24/7 (free tier sleeps after 15 min idle but wakes in ~30s on request).

---

## One-time setup (~10 minutes)

### Step 1 — Router port forwarding

In your router admin page (usually http://192.168.1.1 or http://192.168.0.1):

1. Find **Port Forwarding** (sometimes under Advanced → NAT)
2. Add a rule:
   - **Protocol**: UDP
   - **External port**: 9
   - **Internal IP**: your PC's local IP (e.g. 192.168.1.50) — find it with `ipconfig` → IPv4 Address
   - **Internal port**: 9
3. Save

> **Find your router's external IP**: Google "what is my ip" from your home network.
> This can change occasionally — if WoL stops working, check it and update `ROUTER_IP` in Render.

### Step 2 — Deploy to Render

1. Go to **[render.com](https://render.com)** → sign up free (no credit card)
2. Click **New → Web Service**
3. Connect your GitHub account → select `Stock_bot-tracker` repo
4. Set **Root Directory** to `wol_relay`
5. Set **Build Command**: `pip install -r requirements.txt`
6. Set **Start Command**: `gunicorn app:app`
7. Click **Advanced** → add these **Environment Variables**:

   | Key          | Value                              |
   |---|---|
   | `PC_MAC`     | `BC-F4-D4-A9-18-D1`               |
   | `ROUTER_IP`  | your home router's external IP     |
   | `WOL_PORT`   | `9`                                |
   | `WAKE_SECRET`| any random string (e.g. `abc123xyz`) |

8. Click **Create Web Service** — Render deploys it (~2 min)
9. Copy your Render URL (e.g. `https://stockbot-wol.onrender.com`)

### Step 3 — Update docs/config.js

Edit `docs/config.js` in the repo:

```js
window.WAKE_RELAY_URL = "https://stockbot-wol.onrender.com";
window.WAKE_TOKEN     = "abc123xyz";   // same as WAKE_SECRET above
```

Commit and push — the GitHub Pages Wake PC button is now live.

---

## How it works

```
Phone browser (GitHub Pages)
    ↓  POST /wake
Render.com (this app, always on)
    ↓  UDP magic packet to ROUTER_IP:9
Home router
    ↓  port-forwards to PC's local IP:9
PC's network card (powered by standby 5V)
    ↓  detects magic packet → powers on PC
Windows boots → bot starts → ngrok opens
    ↓  ~2-3 minutes later
GitHub Pages auto-connects ✓
```

---

## Troubleshooting

**Wake button shows "Cannot reach relay"**
→ Check `WAKE_RELAY_URL` in `docs/config.js` — make sure it matches your Render URL exactly.

**Relay responds OK but PC doesn't wake**
→ Port forwarding not set up, or WoL not enabled in BIOS/Windows.
→ Check BIOS: look for "Wake on LAN" or "PCI-E Wake" → Enable.
→ Check Windows: Device Manager → Network Adapters → right-click adapter →
  Properties → Power Management → tick "Allow this device to wake the computer".

**PC wakes but bot doesn't start**
→ Run `setup_remote.bat` to register the Task Scheduler auto-start job.

**Render app is sleeping (first request after 15 min idle takes ~30s)**
→ This is normal on the free tier. The Wake PC button waits for the relay;
  the boot countdown only starts after the relay responds.
