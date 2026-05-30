from datetime import datetime, timezone

import discord

import db


def get_remaining():
    advance_end = db.get_setting("advance_end", "")

    if not advance_end:
        return None

    end = datetime.fromisoformat(advance_end)
    return end - datetime.now(timezone.utc)


def make_status_embed(guild):
    players = db.get_players()
    ready_ids = set(db.get_ready_players())

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
    stage = db.get_setting("advance_stage", "")

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

    elif remaining and remaining.total_seconds() <= 0:
        color = discord.Color.red()
        description = "🚨 **Dynasty is ready to advance!**"

        if stage:
            description += f"\n🏟️ **Current Stage:** {stage}"

    else:
        color = discord.Color.dark_grey()
        description = (
            f"❌ **No active advance.**\n"
            f"📅 **Default Length:** {db.get_setting('advance_days', '4')} day(s)"
        )

        if stage:
            description += f"\n🏟️ **Current Stage:** {stage}"

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
            "`/clearready` — Clear all ready statuses\n"
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
