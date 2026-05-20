import os
from pathlib import Path


def default_db_path() -> Path:
    return Path.home() / ".finance-cli" / "finance.db"


def resolve_db_path() -> Path:
    override = os.environ.get("FINANCE_CLI_DB")
    if override:
        return Path(override).expanduser()
    return default_db_path()
