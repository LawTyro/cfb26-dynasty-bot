import os
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_timers = {}

async def dynasty_countdown(channel, days=4):
    messages = [
        f"🏈 Dynasty advances in {days} days!",
        "⏳ 3 days remaining until advance.",
        "⏳ 2 days remaining until advance.",
        "⚠️ 1 day remaining until advance.",
        "🚨 Dynasty is advancing now!"
    ]

    for i, message in enumerate(messages):
        await channel.send(message)

        # Don't sleep after the last message
        if i < len(messages) - 1:
            await asyncio.sleep(60 * 60 * 24)  # 24 hours


@bot.command()
@commands.has_permissions(administrator=True)
async def advance(ctx):
    """Starts a new 4-day dynasty countdown."""

    guild_id = ctx.guild.id

    # Cancel existing timer if one exists
    if guild_id in active_timers:
        active_timers[guild_id].cancel()

    task = asyncio.create_task(dynasty_countdown(ctx.channel))
    active_timers[guild_id] = task

    await ctx.message.add_reaction("✅")


@bot.command()
@commands.has_permissions(administrator=True)
async def canceladvance(ctx):
    """Cancels the current countdown."""

    guild_id = ctx.guild.id

    if guild_id in active_timers:
        active_timers[guild_id].cancel()
        del active_timers[guild_id]
        await ctx.send("🛑 Dynasty countdown cancelled.")
    else:
        await ctx.send("No active dynasty countdown found.")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


bot.run(TOKEN)
