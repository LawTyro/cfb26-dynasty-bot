import os
import json
import math
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

DATA_FILE = "dynasty.json"

data = {
    "players": [],
    "ready": [],
    "team_history": {},
    "advance_end": None,
    "channel_id": None,
    "last_reminder_day": None,
    "all_ready_sent": False,
    "advance_days": 4
}


def save():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


def load():
    global data

    try:
        with open(DATA_FILE, "r") as f:
            loaded = json.load(f)
            data.update(loaded)

        if "team_history" not in data:
            data["team_history"] = {}

        if "teams" in data:
            for uid, team in data["teams"].items():
                if team:
                    data["team_history"].setdefault(uid, [])
                    if team not in data["team_history"][uid]:
                        data["team_history"][uid].append(team)
            del data["teams"]
            save()

    except FileNotFoundError:
        save()


def get_remaining():
    if not data["advance_end"]:
        return None

    end = datetime.fromisoformat(data["advance_end"])
    return end - datetime.now(timezone.utc)


def everyone_ready():
    return bool(data["players"]) and all(
        player in data["ready"]
        for player in data["players"]
    )


def get_unready_mentions():
    return [
        f"<@{uid}>"
        for uid in data["players"]
        if uid not in data["ready"]
    ]


def get_history(uid):
    return data["team_history"].get(str(uid), [])


async def reminder_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            if data["advance_end"]:
                remaining = get_remaining()

                if remaining:
                    seconds = remaining.total_seconds()

                    if seconds <= 0:
                        channel = bot.get_channel(data["channel_id"])

                        if channel:
                            await channel.send(
                                "🚨 @everyone DYNASTY IS ADVANCING NOW!",
                                allowed_mentions=discord.AllowedMentions(everyone=True)
                            )

                        data["advance_end"] = None
                        data["ready"] = []
                        data["all_ready_sent"] = False
                        save()

                    else:
                        days_left = math.ceil(seconds / 86400)

                        if data["last_reminder_day"] != days_left:
                            data["last_reminder_day"] = days_left

                            channel = bot.get_channel(data["channel_id"])

                            if channel:
                                unready = get_unready_mentions()

                                msg = f"🏈 **{days_left} day(s) until advance**\n"

                                if unready:
                                    msg += "\n❌ Still waiting on:\n"
                                    msg += "\n".join(f"- {mention}" for mention in unready)
                                else:
                                    msg += "\n✅ Everyone is ready."

                                await channel.send(
                                    msg,
                                    allowed_mentions=discord.AllowedMentions(users=True)
                                )

                            save()

        except Exception as e:
            print("Reminder error:", e)

        await asyncio.sleep(60)


player_group = app_commands.Group(
    name="player",
    description="Player management"
)

team_group = app_commands.Group(
    name="team",
    description="Team history commands"
)


@player_group.command(name="add", description="Add player")
@app_commands.checks.has_permissions(administrator=True)
async def player_add(interaction: discord.Interaction, member: discord.Member):
    if member.id in data["players"]:
        return await interaction.response.send_message("Already added.", ephemeral=True)

    data["players"].append(member.id)
    data["team_history"].setdefault(str(member.id), [])
    save()

    await interaction.response.send_message(f"✅ Added {member.display_name}")


@player_group.command(name="remove", description="Remove player")
@app_commands.checks.has_permissions(administrator=True)
async def player_remove(interaction: discord.Interaction, member: discord.Member):
    if member.id not in data["players"]:
        return await interaction.response.send_message("Not found.", ephemeral=True)

    data["players"].remove(member.id)

    if member.id in data["ready"]:
        data["ready"].remove(member.id)

    save()

    await interaction.response.send_message(f"🛑 Removed {member.display_name}")


@player_group.command(name="list", description="List players")
async def player_list(interaction: discord.Interaction):
    guild = interaction.guild
    lines = []

    for uid in data["players"]:
        member = guild.get_member(uid)

        if not member:
            continue

        status = "✅" if uid in data["ready"] else "❌"
        lines.append(f"{status} {member.display_name}")

    await interaction.response.send_message("\n".join(lines) if lines else "No players.")


@team_group.command(name="add", description="Add a team to your history")
async def team_add(interaction: discord.Interaction, team: str):
    uid = interaction.user.id

    if uid not in data["players"]:
        return await interaction.response.send_message("Not registered.", ephemeral=True)

    history = data["team_history"].setdefault(str(uid), [])

    if team in history:
        return await interaction.response.send_message(
            f"**{team}** is already in your team history.",
            ephemeral=True
        )

    history.append(team)
    save()

    await interaction.response.send_message(f"🏈 Added **{team}** to your team history.")


@team_group.command(name="remove", description="Remove a team from your history")
async def team_remove(interaction: discord.Interaction, team: str):
    uid = interaction.user.id
    history = data["team_history"].setdefault(str(uid), [])

    match = next((t for t in history if t.lower() == team.lower()), None)

    if not match:
        return await interaction.response.send_message(
            f"**{team}** was not found in your team history.",
            ephemeral=True
        )

    history.remove(match)
    save()

    await interaction.response.send_message(f"🧹 Removed **{match}** from your team history.")


@team_group.command(name="reset", description="Reset team history for a player or everyone")
@app_commands.checks.has_permissions(administrator=True)
async def team_reset(
    interaction: discord.Interaction,
    member: discord.Member = None,
    all_players: bool = False
):
    if all_players:
        data["team_history"] = {str(uid): [] for uid in data["players"]}
        save()
        return await interaction.response.send_message("🧹 Reset team history for all players.")

    target = member or interaction.user

    data["team_history"][str(target.id)] = []
    save()

    await interaction.response.send_message(f"🧹 Reset team history for {target.display_name}.")


player_group.add_command(team_group)
tree.add_command(player_group)


@tree.command(name="history", description="Show team history")
async def history(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    teams = get_history(target.id)

    if not teams:
        return await interaction.response.send_message(
            f"🏈 {target.display_name} has no team history yet."
        )

    msg = f"🏈 **{target.display_name}'s Team History**\n"
    msg += "\n".join(f"- {team}" for team in teams)

    await interaction.response.send_message(msg)


@tree.command(name="historyall", description="Show team history for all players")
async def historyall(interaction: discord.Interaction):
    guild = interaction.guild
    sections = []

    for uid in data["players"]:
        member = guild.get_member(uid)

        if not member:
            continue

        teams = get_history(uid)

        if teams:
            section = f"**{member.display_name}**\n"
            section += "\n".join(f"- {team}" for team in teams)
        else:
            section = f"**{member.display_name}**\n- No team history"

        sections.append(section)

    if not sections:
        return await interaction.response.send_message("No players found.")

    msg = "🏈 **TEAM HISTORIES**\n\n" + "\n\n".join(sections)

    await interaction.response.send_message(msg)


@tree.command(name="advance", description="Start/reset advance timer")
@app_commands.checks.has_permissions(administrator=True)
async def advance(interaction: discord.Interaction):
    days = data.get("advance_days", 4)
    new_end = datetime.now(timezone.utc) + timedelta(days=days)

    data["advance_end"] = new_end.isoformat()
    data["channel_id"] = interaction.channel.id
    data["ready"] = []
    data["last_reminder_day"] = None
    data["all_ready_sent"] = False

    save()

    await interaction.response.send_message(
        f"@everyone 🏈 Advance timer started! Advance is in {days} day(s).",
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )


@tree.command(name="cancel", description="Cancel advance")
@app_commands.checks.has_permissions(administrator=True)
async def cancel(interaction: discord.Interaction):
    data["advance_end"] = None
    data["ready"] = []
    data["all_ready_sent"] = False

    save()

    await interaction.response.send_message("🛑 Advance cancelled")


@tree.command(name="extend", description="Extend timer")
@app_commands.checks.has_permissions(administrator=True)
async def extend(interaction: discord.Interaction, days: int):
    remaining = get_remaining()

    if not remaining:
        return await interaction.response.send_message("No active advance.")

    new_end = datetime.now(timezone.utc) + remaining + timedelta(days=days)

    data["advance_end"] = new_end.isoformat()
    save()

    await interaction.response.send_message(f"⏳ Extended by {days} day(s).")


@tree.command(name="setdays", description="Set default advance days")
@app_commands.checks.has_permissions(administrator=True)
async def setdays(interaction: discord.Interaction, days: int):
    if days <= 0:
        return await interaction.response.send_message(
            "Days must be greater than 0.",
            ephemeral=True
        )

    data["advance_days"] = days
    save()

    await interaction.response.send_message(
        f"✅ Default advance length set to {days} day(s)."
    )


@tree.command(name="ready", description="Mark ready")
async def ready(interaction: discord.Interaction):
    uid = interaction.user.id

    if uid not in data["players"]:
        return await interaction.response.send_message("Not registered.", ephemeral=True)

    if uid in data["ready"]:
        return await interaction.response.send_message("Already ready.", ephemeral=True)

    data["ready"].append(uid)
    save()

    await interaction.response.send_message("✅ Ready!")

    if data["advance_end"] and everyone_ready() and not data["all_ready_sent"]:
        data["all_ready_sent"] = True
        save()

        channel = bot.get_channel(data["channel_id"])

        if channel:
            commissioner_role = discord.utils.get(
                channel.guild.roles,
                name="Commissioners"
            )

            commissioner_ping = (
                commissioner_role.mention
                if commissioner_role
                else "@Commissioners"
            )

            await channel.send(
                f"🏈 Everyone is ready! {commissioner_ping} advance the league!",
                allowed_mentions=discord.AllowedMentions(roles=True)
            )


@tree.command(name="unready", description="Mark unready")
async def unready(interaction: discord.Interaction):
    uid = interaction.user.id

    if uid in data["ready"]:
        data["ready"].remove(uid)
        data["all_ready_sent"] = False
        save()

    await interaction.response.send_message("↩️ Unready")


@tree.command(name="status", description="Show dynasty status")
async def status(interaction: discord.Interaction):
    guild = interaction.guild

    ready_players = []
    unready_players = []

    for uid in data["players"]:
        member = guild.get_member(uid)

        if not member:
            continue

        if uid in data["ready"]:
            ready_players.append(member.display_name)
        else:
            unready_players.append(member.display_name)

    remaining = get_remaining()

    if remaining and remaining.total_seconds() > 0:
        d = remaining.days
        h = remaining.seconds // 3600
        m = (remaining.seconds % 3600) // 60

        msg = (
            "🏈 ADVANCE STATUS\n"
            f"⏳ Time Left: {d}d {h}h {m}m\n"
            f"📅 Default Length: {data.get('advance_days', 4)} day(s)\n\n"
        )
    elif remaining and remaining.total_seconds() <= 0:
        msg = "🏈 ADVANCE STATUS\n🚨 Dynasty is ready to advance!\n\n"
    else:
        msg = (
            "🏈 ADVANCE STATUS\n"
            "❌ No active advance.\n"
            f"📅 Default Length: {data.get('advance_days', 4)} day(s)\n\n"
        )

    msg += "✅ READY:\n" + "\n".join(ready_players or ["Nobody"])
    msg += "\n\n❌ NOT READY:\n" + "\n".join(unready_players or ["Nobody"])

    await interaction.response.send_message(msg)


@bot.event
async def on_ready():
    load()
    await tree.sync()

    print(f"Logged in as {bot.user}")

    if not hasattr(bot, "reminder_task"):
        bot.reminder_task = asyncio.create_task(reminder_loop())


bot.run(TOKEN)
