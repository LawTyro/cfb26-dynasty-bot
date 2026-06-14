from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

import db
import embeds
from backup_utils import create_database_backup
from constants import stage_autocomplete
from utils import get_output_channel


def setup(tree, bot):
    @tree.command(name="advance", description="Start/reset advance timer")
    @app_commands.autocomplete(stage=stage_autocomplete)
    async def advance(interaction: discord.Interaction, stage: str = None):
        days = int(db.get_setting("advance_days", "4"))
        new_end = datetime.now(timezone.utc) + timedelta(days=days)
        selected_stage = stage or ""

        try:
            create_database_backup()
        except Exception as e:
            print("Auto backup failed:", e)

        db.set_setting("advance_end", new_end.isoformat())
        db.set_setting("last_reminder_day", "")
        db.set_bool_setting("all_ready_sent", False)
        db.set_setting("advance_stage", selected_stage)
        db.clear_ready()

        target_channel = get_output_channel(bot, interaction)

        description = f"Advance is in **{days} day(s)**."

        if selected_stage:
            description += f"\nAdvanced to: **{selected_stage}**"

        embed = discord.Embed(
            title="🏈 Advance Timer Started",
            description=description,
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )

        await target_channel.send(
            "@everyone",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )

        await interaction.response.send_message(
            f"✅ Advance started in {target_channel.mention}.",
            ephemeral=True
        )

    @tree.command(name="cancel", description="Cancel advance")
    @app_commands.checks.has_permissions(administrator=True)
    async def cancel(interaction: discord.Interaction):
        db.set_setting("advance_end", "")
        db.clear_ready()
        db.set_bool_setting("all_ready_sent", False)

        target_channel = get_output_channel(bot, interaction)

        embed = discord.Embed(
            title="🛑 Advance Cancelled",
            description="The current advance timer has been cancelled.",
            color=discord.Color.red()
        )

        await target_channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Advance cancellation posted in {target_channel.mention}.",
            ephemeral=True
        )

    @tree.command(name="extend", description="Extend timer")
    @app_commands.checks.has_permissions(administrator=True)
    async def extend(interaction: discord.Interaction, days: int):
        remaining = embeds.get_remaining()

        if not remaining:
            return await interaction.response.send_message("No active advance.", ephemeral=True)

        new_end = datetime.now(timezone.utc) + remaining + timedelta(days=days)

        db.set_setting("advance_end", new_end.isoformat())
        db.set_setting("last_reminder_day", "")

        target_channel = get_output_channel(bot, interaction)

        embed = discord.Embed(
            title="⏳ Advance Timer Extended",
            description=f"Extended by **{days} day(s)**.",
            color=discord.Color.gold()
        )

        await target_channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Extension posted in {target_channel.mention}.",
            ephemeral=True
        )

    @tree.command(name="setdays", description="Set default advance days")
    @app_commands.checks.has_permissions(administrator=True)
    async def setdays(interaction: discord.Interaction, days: int):
        if days <= 0:
            return await interaction.response.send_message("Days must be greater than 0.", ephemeral=True)

        db.set_setting("advance_days", days)

        embed = discord.Embed(
            title="✅ Default Advance Length Updated",
            description=f"Default advance length set to **{days} day(s)**.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
