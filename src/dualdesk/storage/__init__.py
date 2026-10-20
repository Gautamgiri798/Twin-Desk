"""DualDesk storage module: SQLite repository, settings, devices, migrations and secure secret storage."""
from dualdesk.storage.db import DualDeskDB, get_default_db_path

__all__ = ["DualDeskDB", "get_default_db_path"]
