# -*- coding: utf-8 -*-
"""AI建模助手配置管理"""
import os
import json

# 优先使用 main.py 设置的环境变量，避免 BIMBase 编译缓存导致 __file__ 指向 BFATemp
CONFIG_DIR = os.environ.get('AI_MODELING_PLUGIN_DIR')
if not CONFIG_DIR:
    CONFIG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(CONFIG_DIR, "ai_modeling_config.json")

# 调试用日志
def _log(msg):
    try:
        log_path = os.path.join(CONFIG_DIR, "ai_modeling_config_debug.log")
        with open(log_path, 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

_log(f"config.py CONFIG_DIR={CONFIG_DIR}, CONFIG_FILE={CONFIG_FILE}")

DEFAULT_CONFIG = {
    "api_key": "",
    "api_base": "https://api.deepseek.com/chat/completions",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 2000,
    "baidu_api_key": "",
    "baidu_secret_key": "",
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            _log(f"load_config OK: keys={list(cfg.keys())}, baidu_key_len={len(cfg.get('baidu_api_key', ''))}, secret_len={len(cfg.get('baidu_secret_key', ''))}")
            return cfg
        except Exception as e:
            _log(f"load_config ERROR: {e}")
            import traceback
            _log(traceback.format_exc())
            return dict(DEFAULT_CONFIG)
    _log(f"load_config: file not found: {CONFIG_FILE}")
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_api_key():
    return load_config().get('api_key', '')


def set_api_key(key):
    cfg = load_config()
    cfg['api_key'] = key.strip()
    return save_config(cfg)
