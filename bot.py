import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
import math
from datetime import datetime, timezone

import discord
from discord.ext import commands

import db
import embeds
from utils import get_output_channel, get_unready_mentions
from command_modules import advance, backup, h2h, history, misc, players, readiness, schedule

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


async def reminder_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            remaining = embeds.get_remaining()

            if remaining:
                seconds = remaining.total_seconds()

                if seconds <= 0:
                    channel = get_output_channel(bot)

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

                    db.set_setting("advance_end", "")
                    db.clear_ready()
                    db.set_bool_setting("all_ready_sent", False)

                else:
                    days_left = math.ceil(seconds / 86400)
                    last_reminder_day = db.get_setting("last_reminder_day", "")

                    if str(days_left) != str(last_reminder_day):
                        db.set_setting("last_reminder_day", days_left)

                        channel = get_output_channel(bot)

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


def register_commands():
    players.setup(tree, bot)
    history.setup(tree)
    h2h.setup(tree)
    schedule.setup(tree, bot)
    advance.setup(tree, bot)
    readiness.setup(tree, bot)
    backup.setup(tree, bot)
    misc.setup(tree, bot)


register_commands()


@bot.event
async def on_ready():
    db.init_db()
    db.migrate_json_if_needed()

    synced = await tree.sync()
    print(f"Synced {len(synced)} command(s)")
    print(f"Commands: {[cmd.name for cmd in synced]}")
    print(f"Logged in as {bot.user}")

    if not hasattr(bot, "reminder_task"):
        bot.reminder_task = asyncio.create_task(reminder_loop())


bot.run(TOKEN)
