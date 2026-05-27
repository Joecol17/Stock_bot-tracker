# Remote & Headless Operation Guide

How to run the Stock Bot without being physically at your PC.

---

## Quick start

1. **Double-click `setup_remote.bat`** (run as Administrator)  
   → Registers auto-start in Task Scheduler  
   → Downloads cloudflared for remote dashboard access  
   → Sets up optional auto-shutdown  

2. **Configure BIOS scheduled wake** (see below)  

3. **Done.** The PC boots itself, the bot starts automatically, and you view the dashboard from your phone.

---

## How it works end-to-end

```
BIOS timer (e.g. 3:30 PM)
    ↓ PC powers on
Windows auto-login
    ↓ 2 minutes later
Task Scheduler runs headless_launcher.py
    ├── Starts Cloudflare tunnel → public URL in sidebar
    ├── Starts Flask dashboard (port 5000)
    └── Starts trading bot (auto_trader.py)
           ↓ runs daily analysis (~30 min)
           ↓ bot enters 24h sleep
    (optional) PC auto-shuts down 2 min later
```

You open the **tunnel URL** on your phone to watch the dashboard live.

---

## BIOS Scheduled Wake (auto power-on)

This is the only step that can't be automated — every motherboard is different. The setting is usually called **"RTC Alarm"**, **"Power On by RTC"**, or **"Scheduled Power On"**.

### Common BIOS paths

| Manufacturer | Path |
|---|---|
| **ASUS** | Advanced → APM Configuration → Power On By RTC |
| **Gigabyte** | Power → Power On by Alarm |
| **MSI** | Advanced → ACPI Settings → RTC Alarm |
| **ASRock** | Configuration → ACPI Configuration → Power On By RTC |
| **Dell** | Power Management → Wake on Timer |
| **HP** | Advanced → Built-in Device Options → Wake on Timer |

### Steps
1. Restart your PC and press **Delete**, **F2**, or **F10** during boot (varies by brand)
2. Navigate to the power/ACPI settings section
3. Enable **RTC Wake** and set the time (use UTC if asked — UK time is UTC+0 in winter, UTC+1 in summer)
4. Set to **Daily** or **Every Day** repeat
5. Save and exit

**Recommended time:** 30–60 minutes before US market close (US markets close at 4 PM ET = 9 PM UK)

---

## Wake-on-LAN (manual wake from phone)

Use this when you want to turn the PC on on-demand rather than on a fixed schedule.

### Requirements
- PC must be connected via **ethernet cable** (WiFi WoL is unreliable)
- WoL must be enabled in BIOS and network adapter settings

### Enable in Windows
1. Open **Device Manager** → **Network Adapters** → right-click your ethernet adapter → **Properties**
2. **Power Management** tab → check all three "Wake on" options
3. **Advanced** tab → set **Wake on Magic Packet** to **Enabled**

### Enable in BIOS
Look for **"Wake on LAN"** or **"PCI-E Wake"** in your BIOS power settings and enable it.

### Your PC's MAC address
Run `setup_remote.bat` — it prints your MAC address at the end.  
Or run this in PowerShell: `getmac /fo table`

### Phone apps
| Platform | App |
|---|---|
| Android | **Wake On Lan** (free) |
| iPhone | **Mocha WOL** or **RemoteBoot WOL** (free) |

Enter your PC's MAC address and your home network's broadcast address (usually `192.168.1.255`).

### WoL from outside your home network
Requires either:
- **Tailscale** (easiest — free, install on PC and phone, works anywhere)
- **Port forwarding** UDP port 9 on your router → PC's IP

**Tailscale** is strongly recommended — install on both PC and phone, and you can send WoL packets from anywhere in the world.

---

## Remote dashboard access

### Option A — Quick Tunnel (temporary, no setup needed)
- `setup_remote.bat` downloads `cloudflared.exe` automatically
- When the bot starts, a public URL like `https://random-name.trycloudflare.com` appears in the dashboard sidebar
- **The URL changes every restart** — use Option B or C for a permanent URL

### Option B — ngrok free static domain (permanent, 100% free) ⭐
Run **`setup_ngrok.bat`** — completely free, no credit card, takes ~5 minutes:

1. Double-click **`setup_ngrok.bat`**
2. It downloads ngrok and opens [dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup) instructions
3. You paste your authtoken (from the ngrok dashboard)
4. Go to [dashboard.ngrok.com/domains](https://dashboard.ngrok.com/domains) → click **New Domain** → copy your free domain (e.g. `proud-rabbit-definitely.ngrok-free.app`)
5. Paste it in the wizard → done

Your permanent URL is saved to `.env` and `docs/config.js` automatically.  
**Every free ngrok account gets one free static domain.** It never changes.

### Option C — Named Tunnel (permanent URL, needs a domain) ⭐
Run **`setup_named_tunnel.bat`** — it's an interactive wizard that does everything:

1. **`setup_remote.bat`** first (downloads `cloudflared.exe`) — if not done already
2. **`setup_named_tunnel.bat`** — guided 4-step wizard:
   - Logs in to your Cloudflare account (opens browser)
   - Creates a named tunnel called `stockbot`
   - Guides you to assign a permanent hostname
   - Writes `tunnel_config.yml` and updates `docs/config.js`

**What you need:**
- Free Cloudflare account at [cloudflare.com/sign-up](https://cloudflare.com/sign-up)
- A domain added to Cloudflare (or register one via [Cloudflare Registrar](https://cloudflare.com/products/registrar) — many `.com` domains under $10/yr)

**How to assign the public hostname:**
1. After running `setup_named_tunnel.bat` step 2, open [one.dash.cloudflare.com](https://one.dash.cloudflare.com)
2. Navigate to **Networks → Tunnels** → click `stockbot` → **Configure**
3. **Public Hostname** tab → **Add a public hostname**
4. Fill in: Subdomain `dashboard`, pick your domain, Type `HTTP`, URL `localhost:5000`
5. Your URL: `https://dashboard.yourdomain.com` — **permanent, never changes**

Once set up, the bot uses the named tunnel automatically on every start.
The URL is saved in `docs/config.js` so the GitHub Pages remote dashboard always points to it.

### Option D — Tailscale (simplest for private access)
1. Install Tailscale on PC and phone: tailscale.com
2. Sign in with same account on both devices
3. Access dashboard at `http://your-tailscale-ip:5000`
4. URL never changes, fully private, works anywhere

---

## GitHub Pages remote dashboard

The `docs/` folder in this repo is a self-contained mobile dashboard you can host for free on GitHub Pages. It connects to your PC's Flask API through the Cloudflare tunnel and lets you view data + trigger actions from any device, anywhere.

### One-time GitHub setup

1. Push this repo to GitHub (it's already there if you cloned it)
2. Go to **Settings → Pages**
3. Under *Build and deployment*, set **Source** to `Deploy from a branch`
4. Branch: `main` (or `master`), Folder: `/docs`
5. Click **Save** — GitHub will give you a URL like `https://yourusername.github.io/Stock_bot-tracker/`

### Connecting it to your PC

The GitHub Pages site needs to know your PC's Cloudflare tunnel URL. You have two options:

**Option A — Settings panel (easiest, no code)**  
1. Open the GitHub Pages URL on your phone
2. Tap **⚙** in the top-right corner
3. Enter your current tunnel URL (copy it from the local dashboard sidebar)
4. Optionally enter your auth token (see below)
5. Tap **Save & Connect**

These are saved to the browser's localStorage — you only need to do this once per device. When your tunnel URL changes (on each boot with the free ephemeral tunnel), repeat step 3.

**Option B — Named Tunnel (permanent URL, updates automatically) ⭐**  
Run `setup_named_tunnel.bat` — it updates `docs/config.js` with your permanent URL automatically. Then:

```
git add docs/config.js
git commit -m "Set permanent tunnel URL"
git push
```

The GitHub Pages site always points to the right place — no manual updates needed after PC restarts.

### Protecting action buttons with a token

By default, any visitor who knows the URL can trigger actions (Run Cycle, Pause, Shutdown). To restrict this:

1. Add to your `.env`:
   ```
   DASHBOARD_SECRET=some-long-random-string
   ```
2. Enter the same string as the **Auth Token** in the ⚙ Settings panel on the GitHub Pages site (or in `docs/config.js`)

Read and status endpoints (`/api/botdata`) remain open so the dashboard can always display data. Only mutating actions require the token.

---

## Windows auto-login

For the PC to log in automatically after the BIOS wakes it (required for Task Scheduler to run the bot without you touching anything):

1. Press **Win + R**, type **netplwiz**, press Enter
2. Select your account in the list
3. **Uncheck** "Users must enter a username and password to use this computer"
4. Click **OK** and enter your Windows password when prompted
5. Restart and test

> ⚠️ If your PC is in a shared or public space, skip this and use a PIN or biometric — auto-login is only safe for a private home PC.

---

## PC power controls (dashboard sidebar)

The sidebar has a **PC power controls** section (click to expand):

| Button | What it does |
|---|---|
| 💤 Sleep PC | Puts the PC to sleep immediately |
| ⏻ Shutdown (2 min) | Schedules shutdown in 2 minutes (Cancel button appears) |

These work from your phone via the remote tunnel URL.

---

## Auto-shutdown after daily cycle

Set `BOT_AUTO_SHUTDOWN=true` in `.env` (or let `setup_remote.bat` do it).

The PC shuts down 2 minutes after the bot finishes its daily analysis and enters its 24-hour sleep. This is great for saving electricity if the bot only needs to run for 30–60 minutes per day.

**Full automatic daily flow:**
```
3:30 PM  — BIOS powers on PC
3:32 PM  — Windows auto-login
3:34 PM  — Bot starts (Task Scheduler 2-min delay)
4:00 PM  — US market closes, bot runs analysis
4:30 PM  — Analysis complete, bot sleeping
4:32 PM  — PC shuts down automatically
Next day — Repeat
```

---

## Files created by this setup

| File | Purpose |
|---|---|
| `cloudflared.exe` | Cloudflare tunnel binary (gitignored) |
| `tunnel_url.txt` | Current tunnel URL (gitignored, deleted on shutdown) |
| `tunnel_config.yml` | Named tunnel config — **generated by `setup_named_tunnel.bat`**, gitignored |
| `tunnel_config.yml.example` | Template / reference for the config file |
| `headless_launcher.py` | Manages all processes for headless run |
| `launcher.log` | Log of the launcher process (gitignored) |

---

## Troubleshooting

**Bot doesn't start on boot**  
→ Open Task Scheduler (taskschd.msc), find "StockBotTrader", right-click → Run to test  
→ Check `launcher.log` for errors  

**Tunnel URL not appearing in sidebar**  
→ Check `cloudflared.exe` is in the project folder  
→ Check `launcher.log` for tunnel errors  
→ Wait 30 seconds — tunnel takes time to establish  

**PC doesn't wake from BIOS timer**  
→ Confirm setting is saved in BIOS (it can revert if battery dies)  
→ Make sure "Fast Startup" is disabled in Windows: Power Options → Choose what the power buttons do → uncheck Fast Startup  

**WoL not working**  
→ Must be ethernet, not WiFi  
→ Double-check BIOS WoL setting  
→ Ensure PC is fully shut down (not sleeping) — WoL only works from S5 (off) state on most motherboards  
