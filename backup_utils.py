import shutil
from datetime import datetime, timezone
from pathlib import Path

import db


def create_database_backup():
    db_path = Path(db.DB_FILE)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"dynasty_backup_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    return backup_path
