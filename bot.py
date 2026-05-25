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

DATA_FILE = "advances.json"

# guild_id -> {"end_time": ISO string}
active_advances = {}


# ----------------------------
# Persistence helpers
# ----------------------------

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(active_advances, f)


def load_data():
    global active_advances
    try:
        with open(DATA_FILE, "r") as f:
            active_advances = json.load(f)
    except FileNotFoundError:
        active_advances = {}


def get_remaining(guild_id: int):
    if str(guild_id) not in active_advances:
        return None

    end_time = datetime.fromisoformat(active_advances[str(guild_id)]["end_time"])
    now = datetime.now(timezone.utc)

    return end_time - now


# ----------------------------
# Reminder system
# ----------------------------

async def reminder_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        now = datetime.now(timezone.utc)

        for guild_id, data in list(active_advances.items()):
            try:
                end_time = datetime.fromisoformat(data["end_time"])
                channel_id = data["channel_id"]

                channel = bot.get_channel(channel_id)
                if not channel:
                    continue

                remaining = end_time - now
                seconds = remaining.total_seconds()

                # reminders
                if 86340 < seconds < 86400:
                    await channel.send("⏳ @everyone 1 DAY until dynasty advance!")
                elif 21540 < seconds < 21600:
                    await channel.send("⏳ @everyone 6 HOURS until dynasty advance!")
                elif 3540 < seconds < 3600:
                    await channel.send("⏳ @everyone 1 HOUR until dynasty advance!")
                elif seconds <= 0:
                    await channel.send("🚨 @everyone DYNASTY IS ADVANCING NOW!")

                    # remove after completion
                    del active_advances[guild_id]
                    save_data()

            except Exception as e:
                print("Reminder error:", e)

        await asyncio.sleep(60)  # check every minute


# ----------------------------
# Slash Commands
# ----------------------------

@tree.command(name="advance", description="Start or reset dynasty advance countdown")
@app_commands.checks.has_permissions(administrator=True)
async def advance(interaction: discord.Interaction):

    guild_id = str(interaction.guild.id)

    end_time = datetime.now(timezone.utc) + timedelta(days=4)

    active_advances[guild_id] = {
        "end_time": end_time.isoformat(),
        "channel_id": interaction.channel.id
    }

    save_data()

    await interaction.response.send_message(
        "@everyone 🏈 Dynasty advance started (4 days)!",
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )


@tree.command(name="timeleft", description="Check time until dynasty advance")
async def timeleft(interaction: discord.Interaction):

    remaining = get_remaining(interaction.guild.id)

    if not remaining:
        await interaction.response.send_message("No active dynasty advance.")
        return

    if remaining.total_seconds() <= 0:
        await interaction.response.send_message("🚨 The dynasty is ready to advance!")
        return

    days = remaining.days
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60

    await interaction.response.send_message(
        f"⏳ Time left: **{days}d {hours}h {minutes}m**"
    )


# ----------------------------
# Sync + startup
# ----------------------------

@bot.event
async def on_ready():
    load_data()
    await tree.sync()
    print(f"Logged in as {bot.user}")

    bot.loop.create_task(reminder_loop())


bot.run(TOKEN)
