import os
import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SQLITE_API_HOST = "http://192.168.3.56:8080"
DEFAULT_SQLITE_DB = "finance.db"
DEFAULT_CONFIG_PATH = Path("config") / "finance-cli.json"


@dataclass(frozen=True)
class AppConfig:
    sqlite_api_host: str
    sqlite_db: str


def load_config() -> AppConfig:
    config_path = os.environ.get("FINANCE_CLI_CONFIG")
    if config_path:
        data = json.loads(Path(config_path).expanduser().read_text(encoding="utf-8"))
    elif DEFAULT_CONFIG_PATH.exists():
        data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        data = {}

    host = str(data.get("sqlite_api_host", DEFAULT_SQLITE_API_HOST)).strip().rstrip("/")
    db = str(data.get("sqlite_db", DEFAULT_SQLITE_DB)).strip()
    if not host:
        raise ValueError("sqlite_api_host is required")
    if not db:
        raise ValueError("sqlite_db is required")
    if db.startswith("/") or ".." in db.split("/"):
        raise ValueError("sqlite_db must be a relative SQLite API database name")
    if db.count("/") > 1:
        raise ValueError("sqlite_db may contain at most one directory level")

    return AppConfig(sqlite_api_host=host, sqlite_db=db)
