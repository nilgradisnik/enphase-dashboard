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

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     Local Home Network                      │
│                                                             │
│   ┌───────────────────────┐                                 │
│   │   Enphase IQ Gateway  │                                 │
│   │  (Envoy on Local LAN) │                                 │
│   └──────────┬────────────┘                                 │
│              │ HTTPS / Local JWT Auth                       │
│              ▼                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │               Flask Backend Service                 │   │
│   │                                                     │   │
│   │   ┌───────────────────┐     ┌───────────────────┐   │   │
│   │   │  APScheduler Task │     │   Flask Web API   │   │   │
│   │   │  (15-min Polling) │     │  (REST Endpoints) │   │   │
│   │   └─────────┬─────────┘     └─────────▲─────────┘   │   │
│   │             │                         │             │   │
│   │             ▼                         │             │   │
│   │   ┌───────────────────────────────────┴─────────┐   │   │
│   │   │   Database (PostgreSQL / SQLite via ORM)    │   │   │
│   │   │     - meter_readings (Raw 15-min counters)  │   │   │
│   │   │     - daily_stats (Aggregated totals)       │   │   │
│   │   └─────────────────────────────────────────────┘   │   │
│   └───────────────────────────┬─────────────────────────┘   │
│                               │ JSON Over HTTP              │
│                               ▼                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │           Browser Dashboard (Client-Side)           │   │
│   │   Alpine.js (Reactive State) + Chart.js (Trends)    │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
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

## Detailed Documentation

For a deep dive into the mathematical formulas, cumulative meter accumulation theory, timezone boundary translation, and downtime gap interpolation:

📖 See [docs/database_integration.md](docs/database_integration.md)

---

## License

MIT License.
