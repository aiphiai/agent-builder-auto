import json
import os
import uuid
CONFIG_FILE_PATH = "config.json"
def load_config():
    default_config = {"mcp_config": {"get_current_time": {"command": "python", "args": ["./mcp_server_time.py"], "transport": "stdio"}}}
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        save_config(default_config)
        return default_config
    except Exception as e:
        return default_config
def save_config(config):
    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
def random_uuid():
    return str(uuid.uuid4())