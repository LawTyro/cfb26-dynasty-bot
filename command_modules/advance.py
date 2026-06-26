from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

import db
import embeds
from backup_utils import create_database_backup
from constants import stage_autocomplete
from utils import get_output_channel, log_activity


def _next_stage(current_stage: str) -> str:
    """Return the next week label for stages like "Week 1"."""
    current_stage = (current_stage or "").strip()

    if current_stage.lower().startswith("week "):
        try:
            week_number = int(current_stage.split(None, 1)[1])
            return f"Week {week_number + 1}"
        except (IndexError, ValueError):
            pass

    return "Week 1"


def _previous_stage(current_stage: str) -> str:
    """Return the previous week label for stages like "Week 1"."""
    current_stage = (current_stage or "").strip()

    if current_stage.lower().startswith("week "):
        try:
            week_number = int(current_stage.split(None, 1)[1])
            if week_number > 1:
                return f"Week {week_number - 1}"
            return "Week 1"
        except (IndexError, ValueError):
            pass

    return "Week 1"


def setup(tree, bot):
    @tree.command(name="advance", description="Start/reset advance timer")
    @app_commands.autocomplete(stage=stage_autocomplete)
    async def advance(interaction: discord.Interaction, stage: str = None):
        days = int(db.get_setting("advance_days", "4"))
        new_end = datetime.now(timezone.utc) + timedelta(days=days)
        selected_stage = stage or _next_stage(db.get_setting("advance_stage", ""))

        try:
            create_database_backup()
        except Exception as e:
            print("Auto backup failed:", e)

        db.set_setting("advance_end", new_end.isoformat())
        db.set_setting("last_reminder_day", str(days))
        db.set_bool_setting("all_ready_sent", False)
        db.set_setting("advance_stage", selected_stage)
        db.clear_ready()

        description = f"Advance is in **{days} day(s)**."

        if selected_stage:
            description += f"\nAdvanced to: **{selected_stage}**"

        await interaction.response.send_message("✅ Advance started.", ephemeral=True)
        await log_activity(
            bot,
            interaction,
            "🏈 Advance Timer Started",
            description,
            discord.Color.gold()
        )

    @tree.command(name="cancel", description="Cancel advance")
    @app_commands.checks.has_permissions(administrator=True)
    async def cancel(interaction: discord.Interaction):
        db.set_setting("advance_end", "")
        db.clear_ready()
        db.set_bool_setting("all_ready_sent", False)

        await interaction.response.send_message("✅ Advance cancelled.", ephemeral=True)
        await log_activity(
            bot,
            interaction,
            "🛑 Advance Cancelled",
            "The current advance timer has been cancelled.",
            discord.Color.red()
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

        await interaction.response.send_message("✅ Advance extended.", ephemeral=True)
        await log_activity(
            bot,
            interaction,
            "⏳ Advance Timer Extended",
            f"Extended by **{days} day(s)**.",
            discord.Color.gold()
        )

    @tree.command(name="setdays", description="Set default advance days")
    @app_commands.checks.has_permissions(administrator=True)
    async def setdays(interaction: discord.Interaction, days: int):
        if days <= 0:
            return await interaction.response.send_message("Days must be greater than 0.", ephemeral=True)

        db.set_setting("advance_days", days)

        await interaction.response.send_message(
            f"✅ Default advance length set to **{days} day(s)**.",
            ephemeral=True
        )
        await log_activity(
            bot,
            interaction,
            "✅ Default Advance Length Updated",
            f"Default advance length set to **{days} day(s)**.",
            discord.Color.green()
        )

    @tree.command(name="next", description="Advance to next stage without resetting timer")
    @app_commands.checks.has_permissions(administrator=True)
    async def next_stage(interaction: discord.Interaction):
        current_stage = db.get_setting("advance_stage", "")
        new_stage = _next_stage(current_stage)

        db.set_setting("advance_stage", new_stage)

        await interaction.response.send_message(f"✅ Stage updated to **{new_stage}**.", ephemeral=True)
        await log_activity(
            bot,
            interaction,
            "⏭️ Stage Advanced",
            f"Stage changed to: **{new_stage}**",
            discord.Color.green()
        )

    @tree.command(name="previous", description="Go back to previous stage without resetting timer")
    @app_commands.checks.has_permissions(administrator=True)
    async def previous_stage(interaction: discord.Interaction):
        current_stage = db.get_setting("advance_stage", "")
        new_stage = _previous_stage(current_stage)

        if new_stage == current_stage:
            return await interaction.response.send_message("Already at the earliest stage.", ephemeral=True)

        db.set_setting("advance_stage", new_stage)

        await interaction.response.send_message(f"✅ Stage updated to **{new_stage}**.", ephemeral=True)
        await log_activity(
            bot,
            interaction,
            "⏮️ Stage Reverted",
            f"Stage changed to: **{new_stage}**",
            discord.Color.orange()
        )
