import sys
import os
import json
import yaml
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_apscheduler import APScheduler
from enphase_api.local.gateway import Gateway
from db import db, MeterReading, DailyStats

app = Flask(__name__)

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///enphase.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SCHEDULER_API_ENABLED'] = True

db.init_app(app)

# Initialize Scheduler
scheduler = APScheduler()
scheduler.init_app(app)

CONFIG_FILE = 'configuration/config.yml'
SPECS_FILE = 'configuration/system.yml'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f)
    return {"gateway_ip": "envoy.local", "use_https": True}

def load_specs():
    if os.path.exists(SPECS_FILE):
        with open(SPECS_FILE, 'r') as f:
            return yaml.safe_load(f)
    return {}

@app.route('/')
def index():
    config = load_config()
    specs = load_specs()
    return render_template('index.html', config=config, specs=specs)

def get_authenticated_gateway(config):
    protocol = "https" if config.get('use_https', True) else "http"
    host = f"{protocol}://{config['gateway_ip']}"
    gateway = Gateway(host=host)
    gateway.session.verify = False
    
    token = config.get('gateway_token')
    if token and token != "YOUR_BEARER_TOKEN_HERE":
        # Using login() creates a sessionId cookie which is more compatible with some endpoints
        try:
            gateway.login(token)
        except Exception as e:
            print(f"Login failed: {e}")
            # Fallback to header injection if login fails
            gateway.session.headers.update({'Authorization': f'Bearer {token}'})
    return gateway

@app.route('/api/production')
def production_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/ivp/meters/reports/', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/meters')
def meters_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/ivp/meters/readings', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/inventory')
def inventory_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/inventory.json', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/events')
def events_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        # Using home.json alerts as the reliable source for system events
        data = gateway.api_call('/home.json')
        alerts = data.get('alerts', [])
        # Return as a simple list for the UI
        return jsonify({"alerts": alerts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/connectivity')
def connectivity_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/ivp/livedata/status', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/daily')
def daily_history_api():
    try:
        stats = DailyStats.query.order_by(DailyStats.date.asc()).all()
        return jsonify([s.to_dict() for s in stats])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/refresh', methods=['POST'])
def refresh_history_api():
    try:
        from dashboard_services import record_reading
        record_reading(app)
        return jsonify({"status": "success", "message": "Readings pulled and aggregated successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/rebuild', methods=['POST'])
def rebuild_history_api():
    try:
        from dashboard_services import rebuild_all_daily_stats
        rebuild_all_daily_stats(app)
        return jsonify({"status": "success", "message": "Daily stats completely rebuilt in the target timezone."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Scheduled job definitions
@scheduler.task('interval', id='record_readings_job', minutes=15)
def scheduled_fetch():
    from dashboard_services import record_reading
    record_reading(app)

# Create tables and start scheduler
with app.app_context():
    db.create_all()
    # Trigger initial fetch at startup if DB is empty to populate initial record
    try:
        if not MeterReading.query.first():
            print("Database empty. Performing initial readings fetch...")
            from dashboard_services import record_reading
            record_reading(app)
    except Exception as e:
        print(f"Failed to perform initial fetch: {e}")

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler.start()
    print("Background data collection scheduler started.")

if __name__ == '__main__':
    print(f"Starting dashboard.")
    app.run(debug=True, host='0.0.0.0', port=5000)

