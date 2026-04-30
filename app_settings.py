from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = APP_DIR / "settings.json"


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


def get_resources_dir_fallback(db_dir: Path) -> Path:
    """
    旧仕様互換：DBファイルの隣に resources フォルダを作る。
    """
    d = db_dir / "resources"
    d.mkdir(parents=True, exist_ok=True)
    return d
