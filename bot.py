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

# ----------------------------
# DATA
# ----------------------------

data = {
    "players": [],
    "ready": [],
    "advance_end": None,
    "channel_id": None,
    "last_reminder_day": None,
    "all_ready_sent": False
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

            if "all_ready_sent" not in data:
                data["all_ready_sent"] = False

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


def everyone_ready():

    if not data["players"]:
        return False

    return all(
        player in data["ready"]
        for player in data["players"]
    )


def get_unready_names(guild):

    names = []

    for uid in data["players"]:

        if uid not in data["ready"]:

            member = guild.get_member(uid)

            if member:
                names.append(member.display_name)

    return names


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

                        channel = bot.get_channel(
                            data["channel_id"]
                        )

                        if channel:

                            await channel.send(
                                "🚨 @everyone DYNASTY IS ADVANCING NOW!",
                                allowed_mentions=discord.AllowedMentions(
                                    everyone=True
                                )
                            )

                        data["advance_end"] = None
                        data["ready"] = []
                        data["all_ready_sent"] = False

                        save()

                    else:

                        # FIXED DAY CALCULATION
                        days_left = math.ceil(
                            remaining.total_seconds() / 86400
                        )

                        # DAILY REMINDER ONLY
                        if data["last_reminder_day"] != days_left:

                            data["last_reminder_day"] = days_left

                            channel = bot.get_channel(
                                data["channel_id"]
                            )

                            if channel:

                                unready = get_unready_names(
                                    channel.guild
                                )

                                msg = (
                                    f"🏈 **{days_left} day(s) until advance**\n"
                                )

                                if unready:

                                    msg += (
                                        "\n❌ Still waiting on:\n"
                                    )

                                    msg += "\n".join(
                                        f"- {name}"
                                        for name in unready
                                    )

                                else:

                                    msg += (
                                        "\n✅ Everyone is ready."
                                    )

                                await channel.send(msg)

                            save()

        except Exception as e:
            print("Reminder error:", e)

        await asyncio.sleep(60)


# ----------------------------
# PLAYER GROUP
# ----------------------------

player_group = app_commands.Group(
    name="player",
    description="Player management"
)


@player_group.command(
    name="add",
    description="Add player"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def player_add(
    interaction: discord.Interaction,
    member: discord.Member
):

    if member.id in data["players"]:

        return await interaction.response.send_message(
            "Already added.",
            ephemeral=True
        )

    data["players"].append(member.id)

    save()

    await interaction.response.send_message(
        f"✅ Added {member.display_name}"
    )


@player_group.command(
    name="remove",
    description="Remove player"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def player_remove(
    interaction: discord.Interaction,
    member: discord.Member
):

    if member.id not in data["players"]:

        return await interaction.response.send_message(
            "Not found.",
            ephemeral=True
        )

    data["players"].remove(member.id)

    if member.id in data["ready"]:
        data["ready"].remove(member.id)

    save()

    await interaction.response.send_message(
        f"🛑 Removed {member.display_name}"
    )


@player_group.command(
    name="list",
    description="List players"
)
async def player_list(
    interaction: discord.Interaction
):

    guild = interaction.guild

    lines = []

    for uid in data["players"]:

        member = guild.get_member(uid)

        if not member:
            continue

        status = (
            "✅"
            if uid in data["ready"]
            else "❌"
        )

        lines.append(
            f"{status} {member.display_name}"
        )

    msg = "\n".join(lines) if lines else "No players."

    await interaction.response.send_message(msg)


tree.add_command(player_group)


# ----------------------------
# ADVANCE GROUP
# ----------------------------

advance_group = app_commands.Group(
    name="advance",
    description="Advance system"
)


@advance_group.command(
    name="start",
    description="Start advance"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def advance_start(
    interaction: discord.Interaction,
    days: int = 4
):

    end = (
        datetime.now(timezone.utc)
        + timedelta(days=days)
    )

    data["advance_end"] = end.isoformat()

    data["channel_id"] = interaction.channel.id

    data["ready"] = []

    data["all_ready_sent"] = False

    data["last_reminder_day"] = None

    save()

    await interaction.response.send_message(
        "@everyone 🏈 Advance started!",
        allowed_mentions=discord.AllowedMentions(
            everyone=True
        )
    )


@advance_group.command(
    name="cancel",
    description="Cancel advance"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def advance_cancel(
    interaction: discord.Interaction
):

    data["advance_end"] = None

    data["ready"] = []

    data["all_ready_sent"] = False

    save()

    await interaction.response.send_message(
        "🛑 Advance cancelled"
    )


@advance_group.command(
    name="time",
    description="Time left"
)
async def advance_time(
    interaction: discord.Interaction
):

    remaining = get_remaining()

    if not remaining:

        return await interaction.response.send_message(
            "No active advance."
        )

    d = remaining.days
    h = remaining.seconds // 3600
    m = (remaining.seconds % 3600) // 60

    await interaction.response.send_message(
        f"⏳ {d}d {h}h {m}m left"
    )


@advance_group.command(
    name="force",
    description="Force advance immediately"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def advance_force(
    interaction: discord.Interaction
):

    data["advance_end"] = None

    data["ready"] = []

    data["all_ready_sent"] = False

    save()

    await interaction.response.send_message(
        "🚨 Forced advance executed."
    )


@advance_group.command(
    name="extend",
    description="Extend current advance"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def advance_extend(
    interaction: discord.Interaction,
    days: int
):

    remaining = get_remaining()

    if not remaining:

        return await interaction.response.send_message(
            "No active advance."
        )

    new_end = (
        datetime.now(timezone.utc)
        + remaining
        + timedelta(days=days)
    )

    data["advance_end"] = new_end.isoformat()

    save()

    await interaction.response.send_message(
        f"⏳ Extended by {days} day(s)."
    )


tree.add_command(advance_group)


# ----------------------------
# REGISTER
# ----------------------------

@tree.command(
    name="register",
    description="Register for the dynasty"
)
async def register(
    interaction: discord.Interaction
):

    uid = interaction.user.id

    if uid in data["players"]:

        return await interaction.response.send_message(
            "Already registered.",
            ephemeral=True
        )

    data["players"].append(uid)

    save()

    await interaction.response.send_message(
        "✅ Registered."
    )


# ----------------------------
# READY
# ----------------------------

@tree.command(
    name="ready",
    description="Mark ready"
)
async def ready(
    interaction: discord.Interaction
):

    uid = interaction.user.id

    if uid not in data["players"]:

        return await interaction.response.send_message(
            "Not registered.",
            ephemeral=True
        )

    if uid in data["ready"]:

        return await interaction.response.send_message(
            "Already ready.",
            ephemeral=True
        )

    data["ready"].append(uid)

    save()

    await interaction.response.send_message(
        "✅ Ready!"
    )

    # EVERYONE READY CHECK
    if (
        data["advance_end"]
        and everyone_ready()
        and not data["all_ready_sent"]
    ):

        data["all_ready_sent"] = True

        save()

        channel = bot.get_channel(
            data["channel_id"]
        )

        if channel:

            await channel.send(
                "🏈 Everyone is ready! "
                "Advance whenever you'd like."
            )


# ----------------------------
# UNREADY
# ----------------------------

@tree.command(
    name="unready",
    description="Mark unready"
)
async def unready(
    interaction: discord.Interaction
):

    uid = interaction.user.id

    if uid in data["ready"]:

        data["ready"].remove(uid)

        data["all_ready_sent"] = False

        save()

    await interaction.response.send_message(
        "↩️ Unready"
    )


# ----------------------------
# STATUS
# ----------------------------

@tree.command(
    name="status",
    description="Show status"
)
async def status(
    interaction: discord.Interaction
):

    guild = interaction.guild

    ready_players = []
    unready_players = []

    for uid in data["players"]:

        member = guild.get_member(uid)

        if not member:
            continue

        if uid in data["ready"]:
            ready_players.append(
                member.display_name
            )
        else:
            unready_players.append(
                member.display_name
            )

    msg = (
        f"✅ READY:\n"
        + "\n".join(
            ready_players or ["Nobody"]
        )
    )

    msg += (
        f"\n\n❌ NOT READY:\n"
        + "\n".join(
            unready_players or ["Nobody"]
        )
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

    if not hasattr(bot, "reminder_task"):

        bot.reminder_task = asyncio.create_task(
            reminder_loop()
        )


bot.run(TOKEN)
