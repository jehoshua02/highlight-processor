"""
config_helper.py

Helper for loading config.json and accessing nested keys with dot notation.

Usage:
    from config_helper import config
    tags = config('tags.youtube')
"""

import json
import os

_CONFIG_CACHE = None

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

def _load_config():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _CONFIG_CACHE = json.load(f)
    except Exception:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE

def config(key, default=None):
    """Access config.json with dot notation, e.g. config('tags.youtube')."""
    cfg = _load_config()
    parts = key.split('.')
    for part in parts:
        if isinstance(cfg, dict) and part in cfg:
            cfg = cfg[part]
        else:
            return default
    return cfg
