import json
from functools import lru_cache
from pathlib import Path

CONFIG_PATH = Path("config.json")


@lru_cache(maxsize=1)
def get_config():
    return json.loads(CONFIG_PATH.read_text())
