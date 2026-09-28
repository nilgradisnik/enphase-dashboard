# Enphase Local Dashboard ⚡

A self-hosted, lightweight web dashboard for real-time monitoring and historical energy tracking, communicating directly with your **Enphase IQ Gateway (Envoy)** over the local LAN.

Bypasses cloud latency and rate limits to deliver sub-second telemetry, resilient energy accounting, and hardware diagnostics in a zero-build web interface.

---

## Features

- **Direct LAN Telemetry**: Polls local gateway endpoints directly with no dependency on Enlighten cloud uptime.
- **Real-Time Power Flow**: Live gauges for Solar Production, Net Grid Flow (import/export), and total House Consumption with selectable auto-refresh intervals (1s–5s).
- **Resilient Energy Accounting**: Records hardware-level lifetime cumulative active energy counters ($Wh$) every 15 minutes. No data is lost if the collector restarts or stays offline for days.
- **Timezone-Aware Aggregations**: Normalizes naive UTC database entries against your local solar day boundaries.
- **Automated Gap Interpolation**: Detects server downtime outages (>2 hours), distributes the true accumulated delta proportionally across missed days, and marks them with an "Estimated" badge.
- **Split-Phase & Inverter Health**: Monitors Phase A/B voltages, currents, and power factors, alongside individual microinverter operating statuses and serial numbers.
- **Zero-Build Lightweight UI**: Built using [Alpine.js](https://alpinejs.dev/) and [Chart.js](https://www.chartjs.org/) served via Flask—no Node, React, or npm build pipelines required.
- **Native TRMNL E-Ink Display (BYOS)**: Directly serves [TRMNL OG](https://usetrmnl.com) devices via the native TRMNL BYOS protocol. Renders an 800×480 1-bit monochrome "Daily Solar Status" card layout on a configurable cadence (e.g. 10 min) with zero external cloud or headless browser dependencies.

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           Local Home Network                            │
│                                                                         │
│   ┌───────────────────────┐                                             │
│   │   Enphase IQ Gateway  │                                             │
│   │  (Envoy on Local LAN) │                                             │
│   └──────────┬────────────┘                                             │
│              │ HTTPS / Local JWT Auth                                   │
│              ▼                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     Flask Backend Service                       │   │
│   │                                                                 │   │
│   │   ┌───────────────────┐     ┌───────────────────────────────┐   │   │
│   │   │  APScheduler Task │     │         Flask Web API         │   │   │
│   │   │  (15-min Polling) │     │  - REST Endpoints             │   │   │
│   │   │  (10-min TRMNL)   │     │  - TRMNL BYOS (/api/display)  │   │   │
│   │   └─────────┬─────────┘     └───────────────▲───────────────┘   │   │
│   │             │                               │                   │   │
│   │             ▼                               │                   │   │
│   │   ┌─────────────────────────────────────────┴───────────────┐   │   │
│   │   │          Database (PostgreSQL / SQLite via ORM)         │   │   │
│   │   │            - meter_readings (Raw 15-min counters)       │   │   │
│   │   │            - daily_stats (Aggregated totals)            │   │   │
│   │   └─────────────────────────────────────────────────────────┘   │   │
│   └───────────────────────────┬───────────────────┬─────────────────┘   │
│                               │ JSON Over HTTP    │ 1-bit BMP / PNG     │
│                               ▼                   ▼                     │
│   ┌─────────────────────────────────────────┐   ┌───────────────────┐   │
│   │     Browser Dashboard (Client-Side)     │   │  TRMNL OG Device  │   │
│   │  Alpine.js (Reactive) + Chart.js (Live) │   │ (800x480 E-Paper) │   │
│   └─────────────────────────────────────────┘   └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Quickstart

### 1. Configuration

1. Copy the configuration template:
   ```bash
   cp configuration/config_template.yml configuration/config.yml
   ```

2. Edit `configuration/config.yml`:
   ```yaml
   gateway_ip: "envoy.local"       # Local IP or mDNS hostname of your IQ Gateway
   use_https: true                 # Default: true for D7+ firmware
   gateway_token: "YOUR_TOKEN"     # Your Enphase Entrez / Enlighten bearer token
   timezone: "America/New_York"    # Local timezone for daily solar boundary calculations

   # TRMNL e-ink display configuration
   trmnl:
     enabled: true
     refresh_rate_seconds: 600       # How often the TRMNL device wakes up to pull a new screen (e.g. 600 = 10 min)
     render_interval_minutes: 10    # How often the background job re-renders the image
     api_key: "local-trmnl-token"   # Optional device API key / access token
     title: "DAILY SOLAR STATUS"    # Screen title
   ```


3. *(Optional)* Copy and customize your system specs:
   ```bash
   cp configuration/system_template.yml configuration/system.yml
   ```

> **Security Note:** `config.yml` and `system.yml` contain local network credentials and are automatically ignored by both `.gitignore` and `.dockerignore`.

---

### 2. Run with Docker Compose (Recommended)

The project includes a production compose stack pairing the Flask app with a persistent PostgreSQL database:

```bash
docker compose up -d
```

Open your browser to:
```
http://localhost:5000
```

The service will automatically perform an initial data fetch, seed the database, and begin scheduled 15-minute background polling.

---

### 3. Run Locally (Development)

If you prefer running without Docker:

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt PyJWT

# 3. Start the dashboard
python app.py
```

By default, the local app will use a file-backed SQLite database at `instance/enphase.db`.

---

## TRMNL E-Ink Display Integration (BYOS)

The dashboard includes native **Bring Your Own Server (BYOS)** support for [TRMNL](https://usetrmnl.com) OG e-paper displays, eliminating any need for intermediary servers (like `byos_next` or `terminus`), external cloud services, or heavy headless browsers.

### Display Overview
The screen layout is custom-designed for the **800×480 monochrome** e-ink display and features:
- **Header**: Status dot, screen title, and localized "last updated" timestamp.
- **6-Card Live Metric Grid**:
  1. **Today's Solar**: Total production ($kWh$).
  2. **Today's Usage**: Total household consumption ($kWh$).
  3. **Today's Net Grid**: Net energy flow ($kWh$). Dynamically inverts to solid black with white text when exporting solar power to the grid.
  4. **Today's Export**: Energy exported to the grid ($kWh$).
  5. **Today's Import**: Energy imported from the grid ($kWh$).
  6. **Solar Coverage**: Percentage of household energy covered directly by solar generation.
- **Footer**: System status bar showing active integration.

### TRMNL Device Endpoints
- `GET /api/trmnl/setup`: Returns device handshake and configuration instructions.
- `GET /api/trmnl/display`: Polled by TRMNL; returns rotation (`1`), sleep duration, and image URL.
- `GET /api/trmnl/display/current.png` & `GET /api/trmnl/display/current.bmp`: Serves the rendered 1-bit monochrome image.
- `POST /api/trmnl/log`: Ingests and acknowledges device telemetry logs.
- `GET /api/trmnl`: Interactive in-browser display preview simulating the physical TRMNL OG device.

### Setting Up Your TRMNL Device
1. Put your TRMNL OG device into **Setup Mode** (double-click the physical button).
2. Connect to the device's Wi-Fi hotspot (`TRMNL-...`) and navigate to `http://192.168.4.1`.
3. In the Wi-Fi setup captive portal:
   - Navigate to **Advanced** > **Custom Server**.
   - Enable Custom Server and set the URL to your base host without a trailing slash:
     - If using a domain: `https://solar.nil.earth`
     - If using local IP: `http://<YOUR_SERVER_IP>:5000`
   - Set **API Key** to the `api_key` configured in your `config.yml` (default: `local-trmnl-token`).
4. Save and reboot. The TRMNL firmware will automatically contact `/api/setup` and poll `/api/display` to render your solar status screen!


---

## Detailed Documentation

For a deep dive into the mathematical formulas, cumulative meter accumulation theory, timezone boundary translation, and downtime gap interpolation:

📖 See [docs/database_integration.md](docs/database_integration.md)

---

## License

MIT License.
