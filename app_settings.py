from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = APP_DIR / "settings.json"

WINDOW_SIZE_PRESETS = {
    "small": {
        "label": "小",
        "main": "1100x520",
        "payroll_batch": "1280x600",
        "bonus_batch": "1280x660",
        "payroll_editor": "1180x680",
    },
    "medium": {
        "label": "中",
        "main": "1100x585",
        "payroll_batch": "1360x660",
        "bonus_batch": "1450x760",
        "payroll_editor": "1260x760",
    },
    "large": {
        "label": "大",
        "main": "1100x650",
        "payroll_batch": "1500x760",
        "bonus_batch": "1600x820",
        "payroll_editor": "1380x820",
    },
}

WINDOW_SIZE_LABEL_TO_KEY = {
    data["label"]: key for key, data in WINDOW_SIZE_PRESETS.items()
}


def load_settings() -> dict[str, Any]:
    """
    settings.json を読み込む。
    無ければ空dictを返す（コード側のデフォルトで動かす）。
    """
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        # 壊れていてもアプリを落とさない
        return {}


def get_setting(key: str, default: Any = None) -> Any:
    return load_settings().get(key, default)


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def set_setting(key: str, value: Any) -> None:
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


def get_window_size_key() -> str:
    key = str(get_setting("window_size", "small") or "small")
    return key if key in WINDOW_SIZE_PRESETS else "small"


def get_window_geometry(window_name: str) -> str:
    key = get_window_size_key()
    return WINDOW_SIZE_PRESETS[key][window_name]


def set_window_size_by_label(label: str) -> None:
    set_setting("window_size", WINDOW_SIZE_LABEL_TO_KEY.get(label, "small"))


def get_resources_dir_fallback(db_dir: Path) -> Path:
    """
    旧仕様互換：DBファイルの隣に resources フォルダを作る。
    """
    d = db_dir / "resources"
    d.mkdir(parents=True, exist_ok=True)
    return d
