from datetime import datetime, timezone

import discord

import db


STAGE_ORDER = (
    ["Preseason"]
    + [f"Week {i}" for i in range(0, 16)]
    + ["Conference Championship"]
    + [f"Bowl Week {i}" for i in range(1, 5)]
    + [
        "End of Season Recap",
        "Offseason Portal 1",
        "Offseason Portal 2",
        "Offseason Portal 3",
        "Offseason Portal 4",
        "National Signing Day",
        "Training Results",
        "Encourage Transfers",
    ]
)


def get_next_stage(current_stage: str) -> str:
    current_stage = (current_stage or "").strip()

    if not current_stage:
        return "Preseason"

    try:
        index = STAGE_ORDER.index(current_stage)
    except ValueError:
        return "Preseason"

    return STAGE_ORDER[(index + 1) % len(STAGE_ORDER)]


def get_remaining():
    advance_end = db.get_setting("advance_end", "")

    if not advance_end:
        return None

    end = datetime.fromisoformat(advance_end)
    return end - datetime.now(timezone.utc)


def format_opponent(opponent):
    opponent = str(opponent).strip()

    if opponent.lower().startswith("at "):
        return "@ " + opponent[3:].strip()

    return "vs " + opponent


def make_status_embed(guild):
    players = db.get_players()
    ready_ids = set(db.get_ready_players())

    remaining = get_remaining()
    stage = db.get_setting("advance_stage", "")
    next_stage = get_next_stage(stage)

    schedule_by_user = {}

    if stage:
        for user_id, opponent, is_user_game in db.get_schedule_for_week(stage):
            schedule_by_user[user_id] = opponent

    ready_players = []
    unready_players = []

    for uid in players:
        member = guild.get_member(uid)

        if not member:
            continue

        name = member.display_name
        opponent = schedule_by_user.get(uid)

        if opponent:
            player_line = f"{name} {format_opponent(opponent)}"
        else:
            player_line = name

        if uid in ready_ids:
            ready_players.append(player_line)
        else:
            unready_players.append(player_line)

    if remaining and remaining.total_seconds() > 0:
        d = remaining.days
        h = remaining.seconds // 3600
        m = (remaining.seconds % 3600) // 60

        color = discord.Color.green() if len(unready_players) == 0 and players else discord.Color.gold()

        description = (
            f"⏳ **Time Left:** {d}d {h}h {m}m\n"
            f"📅 **Default Length:** {db.get_setting('advance_days', '4')} day(s)"
        )

        if stage:
            description += f"\n🏟️ **Current Stage:** {stage}"
            description += f"\n⏭️ **Next Stage:** {next_stage}"

    elif remaining and remaining.total_seconds() <= 0:
        color = discord.Color.red()
        description = "🚨 **Dynasty is ready to advance!**"

        if stage:
            description += f"\n🏟️ **Current Stage:** {stage}"
            description += f"\n⏭️ **Next Stage:** {next_stage}"

    else:
        color = discord.Color.dark_grey()
        description = (
            f"❌ **No active advance.**\n"
            f"📅 **Default Length:** {db.get_setting('advance_days', '4')} day(s)"
        )

        if stage:
            description += f"\n🏟️ **Current Stage:** {stage}"
            description += f"\n⏭️ **Next Stage:** {next_stage}"

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
            "`/advance` — Start/reset timer and roll stage\n"
            "`/next` — Move to next stage without changing timer\n"
            "`/previous` — Move to previous stage without changing timer\n"
            "`/cancel` — Cancel timer\n"
            "`/extend` — Add days to timer\n"
            "`/setdays` — Set default length\n"
            "`/setchannel` — Set output channel"
        ),
        inline=False
    )

    embed.add_field(
        name="Readiness",
        value=(
            "`/ready` — Mark yourself ready\n"
            "`/setready` — Mark another player ready\n"
            "`/unready` — Remove ready status\n"
            "`/clearready` — Clear all ready statuses\n"
            "`/status` — Show league dashboard"
        ),
        inline=False
    )

    embed.add_field(
        name="Players",
        value=(
            "`/player add` — Add player\n"
            "`/player addall` — Add all server members\n"
            "`/player remove` — Remove player\n"
            "`/player list` — List players\n"
            "`/player alias` — Set spreadsheet alias\n"
            "`/player clearalias` — Clear spreadsheet alias"
        ),
        inline=False
    )

    embed.add_field(
        name="Schedule",
        value=(
            "`/schedule import` — Import Excel schedule\n"
            "`/schedule clear` — Clear imported schedule\n"
            "`/schedule current` — Show current week schedule\n"
            "`/schedule player` — Show one player's schedule"
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
    p1_wins, p2_wins = db.get_h2h_record(player1.id, player2.id)

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

    for uid in db.get_players():
        if uid == player.id:
            continue

        opponent = guild.get_member(uid)

        if not opponent:
            continue

        wins, losses = db.get_h2h_record(player.id, uid)
        lines.append((opponent.display_name, f"{wins}-{losses}"))

    lines.sort(key=lambda item: item[0].lower())

    wins, losses = db.get_player_record(player.id)

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

    for uid in db.get_players():
        member = guild.get_member(uid)

        if not member:
            continue

        wins, losses = db.get_player_record(uid)
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
