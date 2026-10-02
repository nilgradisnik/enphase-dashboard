import os
import yaml
from enphase_api.local.gateway import Gateway

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_FILE = os.path.join(BASE_DIR, 'configuration', 'config.yml')
SPECS_FILE = os.path.join(BASE_DIR, 'configuration', 'system.yml')

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f) or {}
    return {"gateway_ip": "envoy.local", "use_https": True}

def load_specs():
    if os.path.exists(SPECS_FILE):
        with open(SPECS_FILE, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def get_authenticated_gateway(config=None):
    if config is None:
        config = load_config()
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
