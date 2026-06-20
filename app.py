import sys
import os
import json
import yaml
from flask import Flask, render_template, jsonify
from enphase_api.local.gateway import Gateway

app = Flask(__name__)

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

if __name__ == '__main__':
    print(f"Starting dashboard.")
    app.run(debug=True, host='0.0.0.0', port=5000)

