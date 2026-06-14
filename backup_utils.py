import shutil
from datetime import datetime, timezone
from pathlib import Path

import db

MAX_BACKUPS = 5
BACKUP_PREFIX = "dynasty_backup_"
BACKUP_PATTERN = f"{BACKUP_PREFIX}*.db"


def get_backup_dir():
    db_path = Path(db.DB_FILE)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def list_database_backups():
    backup_dir = get_backup_dir()
    backups = sorted(
        backup_dir.glob(BACKUP_PATTERN),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return backups


def prune_old_backups(max_backups=MAX_BACKUPS):
    backups = list_database_backups()

    for old_backup in backups[max_backups:]:
        old_backup.unlink(missing_ok=True)


def create_database_backup():
    db_path = Path(db.DB_FILE)
    backup_dir = get_backup_dir()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"{BACKUP_PREFIX}{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    prune_old_backups()

    return backup_path


def restore_database_backup(filename):
    db_path = Path(db.DB_FILE)
    backup_dir = get_backup_dir()
    backup_path = backup_dir / filename

    if backup_path.parent != backup_dir:
        raise ValueError("Invalid backup filename.")

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {filename}")

    # Preserve a copy of the current DB before overwriting it.
    # Read the requested backup first so pruning cannot remove the file being restored.
    temp_restore_path = backup_dir / "_restore_temp.db"
    shutil.copy2(backup_path, temp_restore_path)

    try:
        pre_restore_backup = create_database_backup()
        shutil.copy2(temp_restore_path, db_path)
    finally:
        temp_restore_path.unlink(missing_ok=True)

    return backup_path, pre_restore_backup
