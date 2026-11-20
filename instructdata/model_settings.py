"""读写本机的模型配置。"""

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from .chat import ModelConfig

SETTINGS_PATH = Path(__file__).resolve().parents[1] / ".streamlit" / "model-settings.json"


def load_model_settings():
    try:
        contents = SETTINGS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    values = json.loads(contents)
    if not isinstance(values, dict) or not all(
        isinstance(values.get(key), str) for key in ("url", "name", "api_key")
    ):
        raise ValueError("模型配置格式无效。")
    return ModelConfig(values["url"], values["name"], values["api_key"])


def save_model_settings(config):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=SETTINGS_PATH.parent,
            prefix="model-settings.", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(asdict(config), temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
        temporary_path.replace(SETTINGS_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
