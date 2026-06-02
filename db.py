import os
import json
import sqlite3
from datetime import datetime, timezone

DB_FILE = os.getenv("DB_FILE", "dynasty.db")
OLD_JSON_FILE = "dynasty.json"


def db_connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    with db_connect() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS player_aliases (
                user_id INTEGER PRIMARY KEY,
                alias TEXT UNIQUE NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ready (
                user_id INTEGER PRIMARY KEY
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS team_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                team TEXT NOT NULL,
                added_at TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS h2h_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_id INTEGER NOT NULL,
                loser_id INTEGER NOT NULL,
                played_at TEXT NOT NULL
            )
        """)

        defaults = {
            "advance_end": "",
            "channel_id": "",
            "last_reminder_day": "",
            "all_ready_sent": "false",
            "advance_days": "4",
            "advance_stage": ""
        }

        for key, value in defaults.items():
            cur.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )

        conn.commit()


def get_setting(key, default=""):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default


def set_setting(key, value):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        conn.commit()


def get_bool_setting(key):
    return get_setting(key, "false") == "true"


def set_bool_setting(key, value):
    set_setting(key, "true" if value else "false")


def get_players():
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM players ORDER BY user_id")
        return [row[0] for row in cur.fetchall()]


def is_player(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM players WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None


def add_player(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO players (user_id) VALUES (?)", (user_id,))
        conn.commit()


def remove_player(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM players WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM ready WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM player_aliases WHERE user_id = ?", (user_id,))
        conn.commit()


def set_player_alias(user_id, alias):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO player_aliases (user_id, alias) VALUES (?, ?)",
            (user_id, alias.strip())
        )
        conn.commit()


def remove_player_alias(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM player_aliases WHERE user_id = ?", (user_id,))
        conn.commit()


def get_player_alias(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT alias FROM player_aliases WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None


def get_user_id_by_alias(alias):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM player_aliases WHERE LOWER(alias) = LOWER(?)",
            (alias.strip(),)
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_ready_players():
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM ready")
        return [row[0] for row in cur.fetchall()]


def mark_ready(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO ready (user_id) VALUES (?)", (user_id,))
        conn.commit()


def mark_unready(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ready WHERE user_id = ?", (user_id,))
        conn.commit()


def clear_ready():
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ready")
        conn.commit()


def add_history(user_id, team):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM team_history WHERE user_id = ? AND LOWER(team) = LOWER(?)",
            (user_id, team)
        )

        if cur.fetchone():
            return False

        cur.execute(
            "INSERT INTO team_history (user_id, team, added_at) VALUES (?, ?, ?)",
            (user_id, team, datetime.now(timezone.utc).isoformat())
        )

        conn.commit()
        return True


def remove_history(user_id, team):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, team FROM team_history WHERE user_id = ? AND LOWER(team) = LOWER(?)",
            (user_id, team)
        )

        row = cur.fetchone()

        if not row:
            return None

        history_id, actual_team = row

        cur.execute("DELETE FROM team_history WHERE id = ?", (history_id,))
        conn.commit()

        return actual_team


def reset_history(user_id=None):
    with db_connect() as conn:
        cur = conn.cursor()

        if user_id is None:
            cur.execute("DELETE FROM team_history")
        else:
            cur.execute("DELETE FROM team_history WHERE user_id = ?", (user_id,))

        conn.commit()


def get_history(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT team FROM team_history WHERE user_id = ? ORDER BY id",
            (user_id,)
        )
        return [row[0] for row in cur.fetchall()]


def add_h2h_game(winner_id, loser_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO h2h_games (winner_id, loser_id, played_at) VALUES (?, ?, ?)",
            (winner_id, loser_id, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()


def remove_latest_h2h_game(winner_id, loser_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM h2h_games
            WHERE winner_id = ? AND loser_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (winner_id, loser_id)
        )

        row = cur.fetchone()

        if not row:
            return False

        cur.execute("DELETE FROM h2h_games WHERE id = ?", (row[0],))
        conn.commit()

        return True


def reset_h2h(player1_id=None, player2_id=None):
    with db_connect() as conn:
        cur = conn.cursor()

        if player1_id is None and player2_id is None:
            cur.execute("DELETE FROM h2h_games")
        else:
            cur.execute(
                """
                DELETE FROM h2h_games
                WHERE
                (winner_id = ? AND loser_id = ?)
                OR
                (winner_id = ? AND loser_id = ?)
                """,
                (player1_id, player2_id, player2_id, player1_id)
            )

        conn.commit()


def get_h2h_record(player1_id, player2_id):
    with db_connect() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM h2h_games WHERE winner_id = ? AND loser_id = ?",
            (player1_id, player2_id)
        )
        p1_wins = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM h2h_games WHERE winner_id = ? AND loser_id = ?",
            (player2_id, player1_id)
        )
        p2_wins = cur.fetchone()[0]

        return p1_wins, p2_wins


def get_player_record(player_id):
    with db_connect() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM h2h_games WHERE winner_id = ?", (player_id,))
        wins = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM h2h_games WHERE loser_id = ?", (player_id,))
        losses = cur.fetchone()[0]

        return wins, losses


def migrate_json_if_needed():
    if not os.path.exists(OLD_JSON_FILE):
        return

    if get_players():
        return

    try:
        with open(OLD_JSON_FILE, "r") as f:
            old = json.load(f)

        for user_id in old.get("players", []):
            add_player(user_id)

        for user_id in old.get("ready", []):
            mark_ready(user_id)

        for user_id, teams in old.get("team_history", {}).items():
            for team in teams:
                add_history(int(user_id), team)

        set_setting("advance_end", old.get("advance_end") or "")
        set_setting("channel_id", old.get("channel_id") or "")
        set_setting("last_reminder_day", old.get("last_reminder_day") or "")
        set_bool_setting("all_ready_sent", old.get("all_ready_sent", False))
        set_setting("advance_days", old.get("advance_days", 4))
        set_setting("advance_stage", old.get("advance_stage", ""))

        print("Migrated dynasty.json into dynasty.db")

    except Exception as e:
        print("JSON migration failed:", e)
