import os
import json
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

DATA_FILE = "leagues.json"


# ----------------------------
# Storage structure:
# {
#   guild_id: {
#       "active_league": "league_name",
#       "leagues": {
#           "league_name": {
#               "end_time": ISO,
#               "channel_id": int,
#               "reminders": {...}
#           }
#       }
#   }
# }
# ----------------------------

data = {}


# ----------------------------
# Persistence
# ----------------------------

def save():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


def load():
    global data
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}


def get_guild(guild_id: int):
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {"active_league": None, "leagues": {}}
    return data[gid]


def get_active_league(guild_id: int):
    guild = get_guild(guild_id)
    name = guild["active_league"]
    if not name:
        return None
    return guild["leagues"].get(name)


def remaining_time(league):
    end = datetime.fromisoformat(league["end_time"])
    return end - datetime.now(timezone.utc)


# ----------------------------
# Reminder system
# ----------------------------

async def reminder_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        now = datetime.now(timezone.utc)

        for guild_id, guild in data.items():
            for name, league in guild["leagues"].items():

                try:
                    end_time = datetime.fromisoformat(league["end_time"])
                    channel = bot.get_channel(league["channel_id"])

                    if not channel:
                        continue

                    seconds = (end_time - now).total_seconds()

                    if "reminders" not in league:
                        league["reminders"] = {"1d": False, "6h": False, "1h": False}

                    r = league["reminders"]

                    if 86340 < seconds < 86400 and not r["1d"]:
                        await channel.send(f"⏳ @everyone {name}: 1 DAY until advance!")
                        r["1d"] = True

                    elif 21540 < seconds < 21600 and not r["6h"]:
                        await channel.send(f"⏳ @everyone {name}: 6 HOURS until advance!")
                        r["6h"] = True

                    elif 3540 < seconds < 3600 and not r["1h"]:
                        await channel.send(f"⏳ @everyone {name}: 1 HOUR until advance!")
                        r["1h"] = True

                    elif seconds <= 0:
                        await channel.send(f"🚨 @everyone {name} IS ADVANCING NOW!")
                        league["end_time"] = None
                        league["reminders"] = {"1d": False, "6h": False, "1h": False}

                        save()

                except Exception as e:
                    print("Reminder error:", e)

        await asyncio.sleep(60)


# ----------------------------
# LEAGUE COMMANDS
# ----------------------------

@tree.command(name="league_create", description="Create a new league")
async def league_create(interaction: discord.Interaction, name: str):

    guild = get_guild(interaction.guild.id)

    if name in guild["leagues"]:
        await interaction.response.send_message("League already exists.", ephemeral=True)
        return

    guild["leagues"][name] = {
        "end_time": None,
        "channel_id": None,
        "reminders": {"1d": False, "6h": False, "1h": False}
    }

    save()

    await interaction.response.send_message(f"League **{name} created**.")


@tree.command(name="league_set", description="Set active league")
async def league_set(interaction: discord.Interaction, name: str):

    guild = get_guild(interaction.guild.id)

    if name not in guild["leagues"]:
        await interaction.response.send_message("League not found.", ephemeral=True)
        return

    guild["active_league"] = name
    save()

    await interaction.response.send_message(f"Active league set to **{name}**.")


# ----------------------------
# ADVANCE SYSTEM
# ----------------------------

@tree.command(name="advance_start", description="Start or reset advance timer")
async def advance_start(interaction: discord.Interaction, days: int = 4):

    league = get_active_league(interaction.guild.id)

    if not league:
        await interaction.response.send_message("No active league set.", ephemeral=True)
        return

    end_time = datetime.now(timezone.utc) + timedelta(days=days)

    league["end_time"] = end_time.isoformat()
    league["channel_id"] = interaction.channel.id
    league["reminders"] = {"1d": False, "6h": False, "1h": False}

    save()

    await interaction.response.send_message(
        f"@everyone 🏈 Advance slated for {days} days!",
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )


@tree.command(name="advance_cancel", description="Cancel active advance timer")
async def advance_cancel(interaction: discord.Interaction):

    league = get_active_league(interaction.guild.id)

    if not league or not league["end_time"]:
        await interaction.response.send_message("No active timer.", ephemeral=True)
        return

    league["end_time"] = None
    league["reminders"] = {"1d": False, "6h": False, "1h": False}

    save()

    await interaction.response.send_message("🛑 Advance timer cancelled.")


@tree.command(name="advance_time", description="Check time until advance")
async def advance_time(interaction: discord.Interaction):

    league = get_active_league(interaction.guild.id)

    if not league or not league["end_time"]:
        await interaction.response.send_message("No active advance.")
        return

    remaining = remaining_time(league)

    if remaining.total_seconds() <= 0:
        await interaction.response.send_message("🚨 Advance is ready now!")
        return

    d = remaining.days
    h = remaining.seconds // 3600
    m = (remaining.seconds % 3600) // 60

    await interaction.response.send_message(f"⏳ Time left: {d}d {h}h {m}m")


# ----------------------------
# BOT STARTUP
# ----------------------------

@bot.event
async def on_ready():
    load()
    await tree.sync()
    print(f"Logged in as {bot.user}")

    bot.loop.create_task(reminder_loop())


bot.run(TOKEN)
