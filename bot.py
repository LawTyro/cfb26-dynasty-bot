import os
import json
import math
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

DB_FILE = "dynasty.db"
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
            "advance_days": "4"
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


def add_player_db(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO players (user_id) VALUES (?)", (user_id,))
        conn.commit()


def remove_player_db(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM players WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM ready WHERE user_id = ?", (user_id,))
        conn.commit()


def is_player(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM players WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None


def get_ready_players():
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM ready")
        return [row[0] for row in cur.fetchall()]


def mark_ready_db(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO ready (user_id) VALUES (?)", (user_id,))
        conn.commit()


def mark_unready_db(user_id):
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ready WHERE user_id = ?", (user_id,))
        conn.commit()


def clear_ready():
    with db_connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ready")
        conn.commit()


def add_history_db(user_id, team):
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


def remove_history_db(user_id, team):
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


def reset_history_db(user_id=None):
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
            SELECT id, played_at
            FROM h2h_games
            WHERE winner_id = ? AND loser_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (winner_id, loser_id)
        )

        row = cur.fetchone()

        if not row:
            return None

        game_id, played_at = row
        cur.execute("DELETE FROM h2h_games WHERE id = ?", (game_id,))
        conn.commit()

        return played_at


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
            add_player_db(user_id)

        for user_id in old.get("ready", []):
            mark_ready_db(user_id)

        for user_id, teams in old.get("team_history", {}).items():
            for team in teams:
                add_history_db(int(user_id), team)

        set_setting("advance_end", old.get("advance_end") or "")
        set_setting("channel_id", old.get("channel_id") or "")
        set_setting("last_reminder_day", old.get("last_reminder_day") or "")
        set_bool_setting("all_ready_sent", old.get("all_ready_sent", False))
        set_setting("advance_days", old.get("advance_days", 4))

        print("Migrated dynasty.json into dynasty.db")

    except Exception as e:
        print("JSON migration failed:", e)


def get_remaining():
    advance_end = get_setting("advance_end", "")

    if not advance_end:
        return None

    end = datetime.fromisoformat(advance_end)
    return end - datetime.now(timezone.utc)


def everyone_ready():
    players = get_players()

    if not players:
        return False

    ready_players = set(get_ready_players())

    return all(player in ready_players for player in players)


def get_unready_mentions():
    ready_players = set(get_ready_players())

    return [
        f"<@{uid}>"
        for uid in get_players()
        if uid not in ready_players
    ]


def make_status_embed(guild):
    players = get_players()
    ready_ids = set(get_ready_players())

    ready_players = []
    unready_players = []

    for uid in players:
        member = guild.get_member(uid)

        if not member:
            continue

        if uid in ready_ids:
            ready_players.append(member.display_name)
        else:
            unready_players.append(member.display_name)

    remaining = get_remaining()

    if remaining and remaining.total_seconds() > 0:
        d = remaining.days
        h = remaining.seconds // 3600
        m = (remaining.seconds % 3600) // 60

        color = discord.Color.green() if len(unready_players) == 0 and players else discord.Color.gold()

        description = (
            f"⏳ **Time Left:** {d}d {h}h {m}m\n"
            f"📅 **Default Length:** {get_setting('advance_days', '4')} day(s)"
        )

    elif remaining and remaining.total_seconds() <= 0:
        color = discord.Color.red()
        description = "🚨 **Dynasty is ready to advance!**"

    else:
        color = discord.Color.dark_grey()
        description = (
            f"❌ **No active advance.**\n"
            f"📅 **Default Length:** {get_setting('advance_days', '4')} day(s)"
        )

    embed = discord.Embed(
        title="🏈 Dynasty Status",
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(
        name=f"✅ Ready ({len(ready_players)})",
        value="\n".join(ready_players) if ready_players else "Nobody",
        inline=False
    )

    embed.add_field(
        name=f"❌ Not Ready ({len(unready_players)})",
        value="\n".join(unready_players) if unready_players else "Nobody",
        inline=False
    )

    embed.set_footer(text="Dynasty Manager")

    return embed


def make_help_embed():
    embed = discord.Embed(
        title="🏈 Dynasty Bot Commands",
        description="Quick command reference.",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Advance",
        value=(
            "`/advance` — Start/reset timer\n"
            "`/cancel` — Cancel timer\n"
            "`/extend` — Add days to timer\n"
            "`/setdays` — Set default length"
        ),
        inline=False
    )

    embed.add_field(
        name="Readiness",
        value=(
            "`/ready` — Mark yourself ready\n"
            "`/unready` — Remove ready status\n"
            "`/status` — Show league dashboard"
        ),
        inline=False
    )

    embed.add_field(
        name="Players",
        value=(
            "`/player add` — Add player\n"
            "`/player remove` — Remove player\n"
            "`/player list` — List players"
        ),
        inline=False
    )

    embed.add_field(
        name="History",
        value=(
            "`/history view` — View player history\n"
            "`/history all` — View all histories\n"
            "`/history add` — Add team history\n"
            "`/history remove` — Remove team history\n"
            "`/history reset` — Reset history"
        ),
        inline=False
    )

    embed.add_field(
        name="Head-to-Head",
        value=(
            "`/head2head add` — Add result\n"
            "`/head2head remove` — Remove latest matching result\n"
            "`/head2head reset` — Reset matchup records\n"
            "`/head2head view` — View matchup record\n"
            "`/head2head player` — View one player's records\n"
            "`/head2head standings` — View overall standings"
        ),
        inline=False
    )

    return embed


def make_h2h_view_embed(player1, player2):
    p1_wins, p2_wins = get_h2h_record(player1.id, player2.id)

    if p1_wins > p2_wins:
        summary = f"**{player1.display_name} leads {p1_wins}-{p2_wins}**"
        color = discord.Color.green()
    elif p2_wins > p1_wins:
        summary = f"**{player2.display_name} leads {p2_wins}-{p1_wins}**"
        color = discord.Color.red()
    else:
        summary = f"**Series tied {p1_wins}-{p2_wins}**"
        color = discord.Color.gold()

    embed = discord.Embed(
        title=f"🏈 {player1.display_name} vs {player2.display_name}",
        description=summary,
        color=color
    )

    embed.add_field(name=player1.display_name, value=f"{p1_wins} win(s)", inline=True)
    embed.add_field(name=player2.display_name, value=f"{p2_wins} win(s)", inline=True)

    return embed


def make_h2h_player_embed(guild, player):
    lines = []

    for uid in get_players():
        if uid == player.id:
            continue

        opponent = guild.get_member(uid)

        if not opponent:
            continue

        wins, losses = get_h2h_record(player.id, uid)
        lines.append((opponent.display_name, f"{wins}-{losses}"))

    lines.sort(key=lambda item: item[0].lower())

    wins, losses = get_player_record(player.id)

    embed = discord.Embed(
        title=f"🏈 {player.display_name} Head-to-Head",
        color=discord.Color.blue()
    )

    embed.description = (
        "\n".join(f"**vs {name}:** {record}" for name, record in lines)
        if lines
        else "No head-to-head records yet."
    )

    embed.set_footer(text=f"Overall: {wins}-{losses}")

    return embed


def make_h2h_standings_embed(guild):
    rows = []

    for uid in get_players():
        member = guild.get_member(uid)

        if not member:
            continue

        wins, losses = get_player_record(uid)
        games = wins + losses
        win_pct = wins / games if games else 0

        rows.append((member.display_name, wins, losses, win_pct))

    rows.sort(key=lambda row: (row[3], row[1]), reverse=True)

    embed = discord.Embed(
        title="🏆 Head-to-Head Standings",
        color=discord.Color.gold()
    )

    if not rows:
        embed.description = "No players found."
    else:
        lines = []

        for idx, (name, wins, losses, win_pct) in enumerate(rows, start=1):
            pct = f"{win_pct:.3f}" if wins + losses else ".000"
            lines.append(f"**{idx}. {name}** — {wins}-{losses} ({pct})")

        embed.description = "\n".join(lines)

    return embed


async def reminder_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            remaining = get_remaining()

            if remaining:
                seconds = remaining.total_seconds()

                if seconds <= 0:
                    channel_id = get_setting("channel_id", "")
                    channel = bot.get_channel(int(channel_id)) if channel_id else None

                    if channel:
                        embed = discord.Embed(
                            title="🚨 Dynasty Is Advancing Now!",
                            description="The advance timer has expired.",
                            color=discord.Color.red(),
                            timestamp=datetime.now(timezone.utc)
                        )

                        await channel.send(
                            "@everyone",
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(everyone=True)
                        )

                    set_setting("advance_end", "")
                    clear_ready()
                    set_bool_setting("all_ready_sent", False)

                else:
                    days_left = math.ceil(seconds / 86400)
                    last_reminder_day = get_setting("last_reminder_day", "")

                    if str(days_left) != str(last_reminder_day):
                        set_setting("last_reminder_day", days_left)

                        channel_id = get_setting("channel_id", "")
                        channel = bot.get_channel(int(channel_id)) if channel_id else None

                        if channel:
                            unready = get_unready_mentions()

                            embed = discord.Embed(
                                title="🏈 Advance Reminder",
                                description=f"**{days_left} day(s) until advance**",
                                color=discord.Color.gold(),
                                timestamp=datetime.now(timezone.utc)
                            )

                            if unready:
                                embed.add_field(
                                    name="❌ Still Waiting On",
                                    value="\n".join(unready),
                                    inline=False
                                )

                                await channel.send(
                                    " ".join(unready),
                                    embed=embed,
                                    allowed_mentions=discord.AllowedMentions(users=True)
                                )
                            else:
                                embed.add_field(
                                    name="✅ Everyone Is Ready",
                                    value="No one is left to ready up.",
                                    inline=False
                                )

                                await channel.send(embed=embed)

        except Exception as e:
            print("Reminder error:", e)

        await asyncio.sleep(60)


player_group = app_commands.Group(
    name="player",
    description="Player management"
)


@player_group.command(name="add", description="Add player")
@app_commands.checks.has_permissions(administrator=True)
async def player_add(interaction: discord.Interaction, member: discord.Member):
    if is_player(member.id):
        return await interaction.response.send_message("Already added.", ephemeral=True)

    add_player_db(member.id)

    await interaction.response.send_message(f"✅ Added {member.display_name}")


@player_group.command(name="remove", description="Remove player")
@app_commands.checks.has_permissions(administrator=True)
async def player_remove(interaction: discord.Interaction, member: discord.Member):
    if not is_player(member.id):
        return await interaction.response.send_message("Not found.", ephemeral=True)

    remove_player_db(member.id)

    await interaction.response.send_message(f"🛑 Removed {member.display_name}")


@player_group.command(name="list", description="List players")
async def player_list(interaction: discord.Interaction):
    guild = interaction.guild
    ready_ids = set(get_ready_players())

    lines = []

    for uid in get_players():
        member = guild.get_member(uid)

        if not member:
            continue

        status = "✅" if uid in ready_ids else "❌"
        lines.append(f"{status} {member.display_name}")

    embed = discord.Embed(
        title="👥 Dynasty Players",
        description="\n".join(lines) if lines else "No players.",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed)


tree.add_command(player_group)


history_group = app_commands.Group(
    name="history",
    description="Team history commands"
)


@history_group.command(name="view", description="View team history")
async def history_view(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    teams = get_history(target.id)

    embed = discord.Embed(
        title=f"🏈 {target.display_name}'s Team History",
        color=discord.Color.blue()
    )

    embed.description = (
        "\n".join(f"- {team}" for team in teams)
        if teams
        else "No team history yet."
    )

    await interaction.response.send_message(embed=embed)


@history_group.command(name="all", description="Show all histories")
async def history_all(interaction: discord.Interaction):
    guild = interaction.guild

    embed = discord.Embed(
        title="🏈 Team Histories",
        color=discord.Color.blue()
    )

    added = 0

    for uid in get_players():
        member = guild.get_member(uid)

        if not member:
            continue

        teams = get_history(uid)

        embed.add_field(
            name=member.display_name,
            value="\n".join(f"- {team}" for team in teams) if teams else "No team history",
            inline=False
        )

        added += 1

        if added >= 25:
            break

    if added == 0:
        embed.description = "No players found."

    await interaction.response.send_message(embed=embed)


@history_group.command(name="add", description="Add team history")
@app_commands.checks.has_permissions(administrator=True)
async def history_add(interaction: discord.Interaction, member: discord.Member, team: str):
    if not is_player(member.id):
        return await interaction.response.send_message(
            "That player is not registered.",
            ephemeral=True
        )

    added = add_history_db(member.id, team)

    if not added:
        return await interaction.response.send_message(
            f"**{team}** already exists in {member.display_name}'s history.",
            ephemeral=True
        )

    await interaction.response.send_message(
        f"🏈 Added **{team}** to {member.display_name}'s history."
    )


@history_group.command(name="remove", description="Remove team history")
@app_commands.checks.has_permissions(administrator=True)
async def history_remove(interaction: discord.Interaction, member: discord.Member, team: str):
    removed = remove_history_db(member.id, team)

    if not removed:
        return await interaction.response.send_message(f"**{team}** not found.", ephemeral=True)

    await interaction.response.send_message(
        f"🧹 Removed **{removed}** from {member.display_name}'s history."
    )


@history_group.command(name="reset", description="Reset history")
@app_commands.checks.has_permissions(administrator=True)
async def history_reset(
    interaction: discord.Interaction,
    member: discord.Member = None,
    all_players: bool = False
):
    if all_players:
        reset_history_db()
        return await interaction.response.send_message("🧹 Reset history for all players.")

    target = member or interaction.user
    reset_history_db(target.id)

    await interaction.response.send_message(f"🧹 Reset history for {target.display_name}.")


tree.add_command(history_group)


h2h_group = app_commands.Group(
    name="head2head",
    description="Head-to-head records"
)


@h2h_group.command(name="add", description="Add a head-to-head result")
@app_commands.checks.has_permissions(administrator=True)
async def h2h_add(interaction: discord.Interaction, winner: discord.Member, loser: discord.Member):
    if winner.id == loser.id:
        return await interaction.response.send_message(
            "Winner and loser cannot be the same player.",
            ephemeral=True
        )

    if not is_player(winner.id) or not is_player(loser.id):
        return await interaction.response.send_message(
            "Both users must be registered players.",
            ephemeral=True
        )

    add_h2h_game(winner.id, loser.id)

    embed = discord.Embed(
        title="🏈 Head-to-Head Result Added",
        description=f"**{winner.display_name}** defeated **{loser.display_name}**.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed)


@h2h_group.command(name="remove", description="Remove latest matching head-to-head result")
@app_commands.checks.has_permissions(administrator=True)
async def h2h_remove(interaction: discord.Interaction, winner: discord.Member, loser: discord.Member):
    if winner.id == loser.id:
        return await interaction.response.send_message(
            "Winner and loser cannot be the same player.",
            ephemeral=True
        )

    removed = remove_latest_h2h_game(winner.id, loser.id)

    if not removed:
        return await interaction.response.send_message(
            f"No matching result found for {winner.display_name} over {loser.display_name}.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="🧹 Head-to-Head Result Removed",
        description=f"Removed latest result: **{winner.display_name}** defeated **{loser.display_name}**.",
        color=discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)


@h2h_group.command(name="reset", description="Reset head-to-head records")
@app_commands.checks.has_permissions(administrator=True)
async def h2h_reset(
    interaction: discord.Interaction,
    player1: discord.Member = None,
    player2: discord.Member = None,
    all_players: bool = False
):
    if all_players:
        reset_h2h()

        embed = discord.Embed(
            title="🧹 Head-to-Head Records Reset",
            description="All head-to-head records have been deleted.",
            color=discord.Color.red()
        )

        return await interaction.response.send_message(embed=embed)

    if not player1 or not player2:
        return await interaction.response.send_message(
            "Provide both players or set all_players to True.",
            ephemeral=True
        )

    if player1.id == player2.id:
        return await interaction.response.send_message(
            "Choose two different players.",
            ephemeral=True
        )

    reset_h2h(player1.id, player2.id)

    embed = discord.Embed(
        title="🧹 Matchup Reset",
        description=(
            f"Removed all head-to-head games between "
            f"**{player1.display_name}** and **{player2.display_name}**."
        ),
        color=discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)


@h2h_group.command(name="view", description="View record between two players")
async def h2h_view(interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
    if player1.id == player2.id:
        return await interaction.response.send_message(
            "Choose two different players.",
            ephemeral=True
        )

    embed = make_h2h_view_embed(player1, player2)
    await interaction.response.send_message(embed=embed)


@h2h_group.command(name="player", description="View one player's head-to-head records")
async def h2h_player(interaction: discord.Interaction, player: discord.Member = None):
    target = player or interaction.user

    embed = make_h2h_player_embed(interaction.guild, target)
    await interaction.response.send_message(embed=embed)


@h2h_group.command(name="standings", description="View overall head-to-head standings")
async def h2h_standings(interaction: discord.Interaction):
    embed = make_h2h_standings_embed(interaction.guild)
    await interaction.response.send_message(embed=embed)


tree.add_command(h2h_group)


@tree.command(name="advance", description="Start/reset advance timer")
@app_commands.checks.has_permissions(administrator=True)
async def advance(interaction: discord.Interaction):
    days = int(get_setting("advance_days", "4"))
    new_end = datetime.now(timezone.utc) + timedelta(days=days)

    set_setting("advance_end", new_end.isoformat())
    set_setting("channel_id", interaction.channel.id)
    set_setting("last_reminder_day", "")
    set_bool_setting("all_ready_sent", False)
    clear_ready()

    embed = discord.Embed(
        title="🏈 Advance Timer Started",
        description=f"Advance is in **{days} day(s)**.",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    await interaction.response.send_message(
        "@everyone",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )


@tree.command(name="cancel", description="Cancel advance")
@app_commands.checks.has_permissions(administrator=True)
async def cancel(interaction: discord.Interaction):
    set_setting("advance_end", "")
    clear_ready()
    set_bool_setting("all_ready_sent", False)

    embed = discord.Embed(
        title="🛑 Advance Cancelled",
        description="The current advance timer has been cancelled.",
        color=discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)


@tree.command(name="extend", description="Extend timer")
@app_commands.checks.has_permissions(administrator=True)
async def extend(interaction: discord.Interaction, days: int):
    remaining = get_remaining()

    if not remaining:
        return await interaction.response.send_message("No active advance.", ephemeral=True)

    new_end = datetime.now(timezone.utc) + remaining + timedelta(days=days)

    set_setting("advance_end", new_end.isoformat())
    set_setting("last_reminder_day", "")

    embed = discord.Embed(
        title="⏳ Advance Timer Extended",
        description=f"Extended by **{days} day(s)**.",
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)


@tree.command(name="setdays", description="Set default advance days")
@app_commands.checks.has_permissions(administrator=True)
async def setdays(interaction: discord.Interaction, days: int):
    if days <= 0:
        return await interaction.response.send_message(
            "Days must be greater than 0.",
            ephemeral=True
        )

    set_setting("advance_days", days)

    embed = discord.Embed(
        title="✅ Default Advance Length Updated",
        description=f"Default advance length set to **{days} day(s)**.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed)


@tree.command(name="ready", description="Mark ready")
async def ready(interaction: discord.Interaction):
    uid = interaction.user.id

    if not is_player(uid):
        return await interaction.response.send_message("Not registered.", ephemeral=True)

    if uid in get_ready_players():
        return await interaction.response.send_message("Already ready.", ephemeral=True)

    mark_ready_db(uid)

    await interaction.response.send_message("✅ Ready!")

    if get_setting("advance_end", "") and everyone_ready() and not get_bool_setting("all_ready_sent"):
        set_bool_setting("all_ready_sent", True)

        channel_id = get_setting("channel_id", "")
        channel = bot.get_channel(int(channel_id)) if channel_id else None

        if channel:
            commissioner_role = discord.utils.get(
                channel.guild.roles,
                name="Commissioners"
            )

            commissioner_ping = commissioner_role.mention if commissioner_role else "@Commissioners"

            embed = discord.Embed(
                title="🏈 Everyone Is Ready!",
                description="Commissioners can advance the league.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )

            await channel.send(
                commissioner_ping,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True)
            )


@tree.command(name="unready", description="Mark unready")
async def unready(interaction: discord.Interaction):
    mark_unready_db(interaction.user.id)
    set_bool_setting("all_ready_sent", False)

    await interaction.response.send_message("↩️ Unready")


@tree.command(name="status", description="Show dynasty status")
async def status(interaction: discord.Interaction):
    embed = make_status_embed(interaction.guild)
    await interaction.response.send_message(embed=embed)


@tree.command(name="help", description="Show commands")
async def help_command(interaction: discord.Interaction):
    embed = make_help_embed()
    await interaction.response.send_message(embed=embed)


@bot.event
async def on_ready():
    init_db()
    migrate_json_if_needed()

    await tree.sync()

    print(f"Logged in as {bot.user}")

    if not hasattr(bot, "reminder_task"):
        bot.reminder_task = asyncio.create_task(reminder_loop())


bot.run(TOKEN)
