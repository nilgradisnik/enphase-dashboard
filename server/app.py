import os
import sys

# Ensure repository root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template
from flask_apscheduler import APScheduler
from server.db import db, MeterReading
from server.config import load_config, load_specs
from server.api import api_bp
from server.trmnl_service import update_trmnl_display, load_trmnl_telemetry

# Configure Flask app with explicit template, static, and instance paths
template_dir = os.path.join(PROJECT_ROOT, 'templates')
static_dir = os.path.join(PROJECT_ROOT, 'static')
instance_dir = os.path.join(PROJECT_ROOT, 'instance')

app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=static_dir,
    instance_path=instance_dir
)

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///enphase.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SCHEDULER_API_ENABLED'] = True

db.init_app(app)

# Register API routes blueprint
app.register_blueprint(api_bp)

# Add backwards-compatibility aliases for view functions in url_map/view_functions
for endpoint in [
    'production_api', 'meters_api', 'inventory_api', 'events_api',
    'connectivity_api', 'daily_history_api', 'monthly_history_api',
    'refresh_history_api', 'trmnl_setup_api', 'trmnl_display_api',
    'trmnl_current_png', 'trmnl_current_bmp', 'trmnl_log_api', 'trmnl_status_api'
]:
    bp_endpoint = f'api.{endpoint}'
    if bp_endpoint in app.view_functions:
        app.view_functions[endpoint] = app.view_functions[bp_endpoint]

# Initialize Scheduler
scheduler = APScheduler()
scheduler.init_app(app)


@app.route('/')
def index():
    config = load_config()
    specs = load_specs()
    return render_template('index.html', config=config, specs=specs)


@app.route('/trmnl', methods=['GET'])
def trmnl_preview_page():
    config = load_config()
    trmnl_cfg = config.get('trmnl', {})
    refresh_rate_sec = int(trmnl_cfg.get('refresh_rate_seconds', 600))
    refresh_rate_min = max(1, refresh_rate_sec // 60)
    telemetry = load_trmnl_telemetry()
    return render_template('trmnl.html', telemetry=telemetry, refresh_rate_min=refresh_rate_min)


# Scheduled job definitions
@scheduler.task('interval', id='record_readings_job', minutes=15)
def scheduled_fetch():
    from server.dashboard_services import record_reading
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
            from server.dashboard_services import record_reading
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
    print("Starting dashboard.")
    app.run(debug=True, host='0.0.0.0', port=5000)
