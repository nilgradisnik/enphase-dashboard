import sys
import os
import time
import json
import yaml
from flask import Flask, render_template, jsonify, send_file, request, make_response
from flask_apscheduler import APScheduler
from enphase_api.local.gateway import Gateway
from db import db, MeterReading, DailyStats
from trmnl_service import update_trmnl_display, OUTPUT_IMAGE_PATH, OUTPUT_BMP_PATH, load_trmnl_telemetry, record_trmnl_checkin, record_trmnl_log_message


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

@app.route('/api/history/monthly')
def monthly_history_api():
    try:
        stats = DailyStats.query.order_by(DailyStats.date.asc()).all()
        monthly_data = {}
        for s in stats:
            month_str = s.date.strftime('%Y-%m')
            if month_str not in monthly_data:
                monthly_data[month_str] = {
                    'month': month_str,
                    'production_kwh': 0.0,
                    'import_kwh': 0.0,
                    'export_kwh': 0.0,
                    'consumption_kwh': 0.0
                }
            monthly_data[month_str]['production_kwh'] += s.production_kwh
            monthly_data[month_str]['import_kwh'] += s.import_kwh
            monthly_data[month_str]['export_kwh'] += s.export_kwh
            monthly_data[month_str]['consumption_kwh'] += s.consumption_kwh
            
        result = []
        for month in sorted(monthly_data.keys()):
            m_data = monthly_data[month]
            result.append({
                'month': m_data['month'],
                'production_kwh': round(m_data['production_kwh'], 2),
                'import_kwh': round(m_data['import_kwh'], 2),
                'export_kwh': round(m_data['export_kwh'], 2),
                'consumption_kwh': round(m_data['consumption_kwh'], 2)
            })
        return jsonify(result)
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

def get_request_base_url():
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    host = request.headers.get('X-Forwarded-Host', request.host)
    return f"{scheme}://{host}".rstrip('/')

# TRMNL e-ink display API routes
@app.route('/api/setup', methods=['GET'])
def trmnl_setup_api():
    config = load_config()
    trmnl_cfg = config.get('trmnl', {})
    api_key = trmnl_cfg.get('api_key', 'local-trmnl-token')
    base_url = get_request_base_url()
    return jsonify({
        "status": 200,
        "api_key": api_key,
        "friendly_id": "TRMNL-SOLAR",
        "image_url": f"{base_url}/api/display/current.bmp",
        "filename": "solar_setup.bmp",
        "message": "TRMNL connected to Enphase solar dashboard"
    })

@app.route('/api/display', methods=['GET'])
def trmnl_display_api():
    config = load_config()
    trmnl_cfg = config.get('trmnl', {})
    refresh_rate = int(trmnl_cfg.get('refresh_rate_seconds', 600))
    base_url = get_request_base_url()

    record_trmnl_checkin(dict(request.headers))

    if not os.path.exists(OUTPUT_BMP_PATH):
        update_trmnl_display(app)

    # TRMNL firmware uses filename comparison to skip refresh if unchanged.
    # Appending mtime ensures TRMNL detects when a new render is available.
    mtime = int(os.path.getmtime(OUTPUT_BMP_PATH)) if os.path.exists(OUTPUT_BMP_PATH) else int(time.time())
    filename = f"solar_{mtime}.bmp"

    return jsonify({
        "status": 0,
        "image_url": f"{base_url}/api/display/current.bmp",
        "filename": filename,
        "refresh_rate": refresh_rate,
        "reset_firmware": False,
        "update_firmware": False,
        "firmware_url": None,
        "special_function": "none",
        "image_rotate": 1
    })

@app.route('/api/display/current.png', methods=['GET'])
def trmnl_current_png():
    if not os.path.exists(OUTPUT_IMAGE_PATH):
        update_trmnl_display(app)
    response = make_response(send_file(OUTPUT_IMAGE_PATH, mimetype='image/png'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/display/current.bmp', methods=['GET'])
def trmnl_current_bmp():
    if not os.path.exists(OUTPUT_BMP_PATH):
        update_trmnl_display(app)
    response = make_response(send_file(OUTPUT_BMP_PATH, mimetype='image/bmp'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/log', methods=['POST'])
def trmnl_log_api():
    log_data = request.get_json(silent=True) or request.form.to_dict() or request.data.decode('utf-8', errors='ignore')
    record_trmnl_log_message(dict(request.headers), log_data)
    return jsonify({"status": 200})


@app.route('/api/display/status', methods=['GET'])
def trmnl_status_api():
    return jsonify(load_trmnl_telemetry())


@app.route('/trmnl', methods=['GET'])
def trmnl_preview_page():
    telemetry = load_trmnl_telemetry()
    return render_template('trmnl.html', telemetry=telemetry)



# Scheduled job definitions
@scheduler.task('interval', id='record_readings_job', minutes=15)
def scheduled_fetch():
    from dashboard_services import record_reading
    record_reading(app)

# TRMNL render scheduled job
config_init = load_config()
trmnl_interval = int(config_init.get('trmnl', {}).get('render_interval_minutes', 10))

@scheduler.task('interval', id='render_trmnl_job', minutes=trmnl_interval)
def scheduled_trmnl():
    cfg = load_config()
    if cfg.get('trmnl', {}).get('enabled', True):
        update_trmnl_display(app)

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

    # Generate initial TRMNL screen
    try:
        cfg = load_config()
        if cfg.get('trmnl', {}).get('enabled', True):
            update_trmnl_display(app)
    except Exception as e:
        print(f"Failed to perform initial TRMNL render: {e}")

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler.start()
    print("Background data collection scheduler started.")

if __name__ == '__main__':
    print(f"Starting dashboard.")
    app.run(debug=True, host='0.0.0.0', port=5000)


