import os
import time
import json
from flask import Blueprint, jsonify, request, send_file, make_response, current_app
from server.db import DailyStats
from server.config import load_config, get_authenticated_gateway
from server.trmnl_service import (
    update_trmnl_display,
    OUTPUT_IMAGE_PATH,
    OUTPUT_BMP_PATH,
    load_trmnl_telemetry,
    record_trmnl_checkin,
    record_trmnl_log_message
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_request_base_url():
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    host = request.headers.get('X-Forwarded-Host', request.host)
    return f"{scheme}://{host}".rstrip('/')


# ---------------------------------------------------------------------------
# Enphase Gateway Proxy Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/production')
def production_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/ivp/meters/reports/', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/meters')
def meters_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/ivp/meters/readings', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/inventory')
def inventory_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/inventory.json', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/events')
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


@api_bp.route('/connectivity')
def connectivity_api():
    config = load_config()
    gateway = get_authenticated_gateway(config)
    try:
        raw_data = gateway.api_call('/ivp/livedata/status', response_raw=True)
        return jsonify(json.loads(raw_data))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Historical Aggregations Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/history/daily')
def daily_history_api():
    try:
        stats = DailyStats.query.order_by(DailyStats.date.asc()).all()
        return jsonify([s.to_dict() for s in stats])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/history/monthly')
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


@api_bp.route('/history/refresh', methods=['POST'])
def refresh_history_api():
    try:
        from server.dashboard_services import record_reading
        record_reading(current_app._get_current_object())
        return jsonify({"status": "success", "message": "Readings pulled and aggregated successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# TRMNL E-Ink Display BYOS Endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/setup', methods=['GET'])
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


@api_bp.route('/display', methods=['GET'])
def trmnl_display_api():
    config = load_config()
    trmnl_cfg = config.get('trmnl', {})
    refresh_rate = int(trmnl_cfg.get('refresh_rate_seconds', 600))
    base_url = get_request_base_url()

    record_trmnl_checkin(dict(request.headers))

    if not os.path.exists(OUTPUT_BMP_PATH):
        update_trmnl_display(current_app._get_current_object())

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


@api_bp.route('/display/current.png', methods=['GET'])
def trmnl_current_png():
    if not os.path.exists(OUTPUT_IMAGE_PATH):
        update_trmnl_display(current_app._get_current_object())
    response = make_response(send_file(OUTPUT_IMAGE_PATH, mimetype='image/png'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@api_bp.route('/display/current.bmp', methods=['GET'])
def trmnl_current_bmp():
    if not os.path.exists(OUTPUT_BMP_PATH):
        update_trmnl_display(current_app._get_current_object())
    response = make_response(send_file(OUTPUT_BMP_PATH, mimetype='image/bmp'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@api_bp.route('/log', methods=['POST'])
def trmnl_log_api():
    log_data = request.get_json(silent=True) or request.form.to_dict() or request.data.decode('utf-8', errors='ignore')
    record_trmnl_log_message(dict(request.headers), log_data)
    return jsonify({"status": 200})


@api_bp.route('/display/status', methods=['GET'])
def trmnl_status_api():
    return jsonify(load_trmnl_telemetry())
