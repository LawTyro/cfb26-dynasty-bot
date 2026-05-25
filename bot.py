import os
import json
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

# ----------------------------
# DATA STRUCTURE
# ----------------------------
# {
#   "players": [user_id],
#   "ready": [user_id],
#   "advance_end": ISO string,
#   "channel_id": int,
#   "last_reminder_day": int
# }
# ----------------------------

data = {
    "players": [],
    "ready": [],
    "advance_end": None,
    "channel_id": None,
    "last_reminder_day": None
}


# ----------------------------
# SAVE / LOAD
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
        save()


# ----------------------------
# HELPERS
# ----------------------------

def get_remaining():
    if not data["advance_end"]:
        return None

    end = datetime.fromisoformat(data["advance_end"])
    return end - datetime.now(timezone.utc)


def get_unready_mentions():
    mentions = []

    for user_id in data["players"]:
        if user_id not in data["ready"]:
            mentions.append(f"<@{user_id}>")

    return " ".join(mentions)


# ----------------------------
# REMINDER LOOP
# ----------------------------

async def reminder_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():

        try:
            if data["advance_end"]:

                remaining = get_remaining()

                if remaining:

                    seconds = remaining.total_seconds()

                    # ADVANCE COMPLETE
                    if seconds <= 0:

                        channel = bot.get_channel(data["channel_id"])

                        if channel:
                            await channel.send(
                                "🚨 @everyone DYNASTY IS ADVANCING NOW!",
                                allowed_mentions=discord.AllowedMentions(
                                    everyone=True
                                )
                            )

                        data["advance_end"] = None
                        save()

                    else:

                        days_left = remaining.days

                        # prevent duplicate daily reminders
                        if data["last_reminder_day"] != days_left:

                            data["last_reminder_day"] = days_left

                            unready_mentions = get_unready_mentions()

                            channel = bot.get_channel(data["channel_id"])

                            if channel and unready_mentions:

                                await channel.send(
                                    f"⏳ {days_left} day(s) until advance.\n"
                                    f"Still waiting on:\n"
                                    f"{unready_mentions}"
                                )

                            save()

        except Exception as e:
            print("Reminder loop error:", e)

        await asyncio.sleep(60)


# ----------------------------
# REGISTER
# ----------------------------

@tree.command(name="register", description="Register for the dynasty")
async def register(interaction: discord.Interaction):

    user_id = interaction.user.id

    if user_id in data["players"]:
        await interaction.response.send_message(
            "You are already registered.",
            ephemeral=True
        )
        return

    data["players"].append(user_id)
    save()

    await interaction.response.send_message(
        "✅ You are now registered for the dynasty."
    )


# ----------------------------
# READY
# ----------------------------

@tree.command(name="ready", description="Mark yourself as ready")
async def ready(interaction: discord.Interaction):

    user_id = interaction.user.id

    if user_id not in data["players"]:
        await interaction.response.send_message(
            "You are not registered.",
            ephemeral=True
        )
        return

    if user_id in data["ready"]:
        await interaction.response.send_message(
            "You are already marked ready.",
            ephemeral=True
        )
        return

    data["ready"].append(user_id)
    save()

    await interaction.response.send_message(
        f"✅ {interaction.user.mention} is ready!"
    )


# ----------------------------
# START ADVANCE
# ----------------------------

@tree.command(name="advance_start", description="Start/reset advance timer")
@app_commands.checks.has_permissions(administrator=True)
async def advance_start(interaction: discord.Interaction, days: int = 4):

    end_time = datetime.now(timezone.utc) + timedelta(days=days)

    data["advance_end"] = end_time.isoformat()
    data["channel_id"] = interaction.channel.id

    # RESET READY STATUS
    data["ready"] = []

    # reset reminder tracking
    data["last_reminder_day"] = None

    save()

    await interaction.response.send_message(
        f"@everyone 🏈 Dynasty advance started! "
        f"Advance is in {days} days.",
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )


# ----------------------------
# CANCEL ADVANCE
# ----------------------------

@tree.command(name="advance_cancel", description="Cancel advance timer")
@app_commands.checks.has_permissions(administrator=True)
async def advance_cancel(interaction: discord.Interaction):

    if not data["advance_end"]:
        await interaction.response.send_message(
            "No active advance.",
            ephemeral=True
        )
        return

    data["advance_end"] = None
    save()

    await interaction.response.send_message(
        "🛑 Advance timer cancelled."
    )


# ----------------------------
# TIME LEFT
# ----------------------------

@tree.command(name="advance_time", description="Check time until advance")
async def advance_time(interaction: discord.Interaction):

    remaining = get_remaining()

    if not remaining:
        await interaction.response.send_message(
            "No active advance."
        )
        return

    if remaining.total_seconds() <= 0:
        await interaction.response.send_message(
            "🚨 Dynasty is ready to advance!"
        )
        return

    d = remaining.days
    h = remaining.seconds // 3600
    m = (remaining.seconds % 3600) // 60

    await interaction.response.send_message(
        f"⏳ Time left: {d}d {h}h {m}m"
    )


# ----------------------------
# LIST STATUS
# ----------------------------

@tree.command(name="status", description="Show dynasty readiness")
async def status(interaction: discord.Interaction):

    ready_mentions = []
    unready_mentions = []

    for user_id in data["players"]:

        if user_id in data["ready"]:
            ready_mentions.append(f"<@{user_id}>")
        else:
            unready_mentions.append(f"<@{user_id}>")

    msg = (
        f"✅ READY ({len(ready_mentions)}):\n"
        f"{' '.join(ready_mentions) if ready_mentions else 'Nobody'}\n\n"
        f"❌ NOT READY ({len(unready_mentions)}):\n"
        f"{' '.join(unready_mentions) if unready_mentions else 'Nobody'}"
    )

    await interaction.response.send_message(msg)


# ----------------------------
# STARTUP
# ----------------------------

@bot.event
async def on_ready():
    load()

    await tree.sync()

    print(f"Logged in as {bot.user}")

    bot.loop.create_task(reminder_loop())


bot.run(TOKEN)
