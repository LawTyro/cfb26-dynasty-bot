from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

import db
import embeds
from backup_utils import create_database_backup
from constants import stage_autocomplete
from utils import get_output_channel, log_activity


STAGE_ORDER = (
    ["Preseason"]
    + [f"Week {i}" for i in range(0, 16)]
    + ["Conference Championship"]
    + [f"Bowl Week {i}" for i in range(1, 5)]
    + [
        "End of Season Recap",
        "Offseason Portal 1",
        "Offseason Portal 2",
        "Offseason Portal 3",
        "Offseason Portal 4",
        "National Signing Day",
        "Training Results",
        "Encourage Transfers",
    ]
)


def get_next_stage(current_stage: str) -> str:
    """Return the next dynasty stage, wrapping back to Preseason at the end."""
    current_stage = (current_stage or "").strip()

    if not current_stage:
        return "Preseason"

    try:
        index = STAGE_ORDER.index(current_stage)
    except ValueError:
        return "Preseason"

    return STAGE_ORDER[(index + 1) % len(STAGE_ORDER)]


def setup(tree, bot):
    @tree.command(name="advance", description="Start/reset advance timer")
    @app_commands.autocomplete(stage=stage_autocomplete)
    async def advance(interaction: discord.Interaction, stage: str = None):
        days = int(db.get_setting("advance_days", "4"))
        new_end = datetime.now(timezone.utc) + timedelta(days=days)
        current_stage = db.get_setting("advance_stage", "")
        selected_stage = stage or get_next_stage(current_stage)

        try:
            create_database_backup()
        except Exception as e:
            print("Auto backup failed:", e)

        db.set_setting("advance_end", new_end.isoformat())

        # Prevent the reminder loop from immediately sending a duplicate
        # "4 days remaining" ping right after /advance starts.
        db.set_setting("last_reminder_day", str(days))

        db.set_bool_setting("all_ready_sent", False)
        db.set_setting("advance_stage", selected_stage)
        db.clear_ready()

        description = f"Advance is in **{days} day(s)**."

        if selected_stage:
            description += f"\nAdvanced to: **{selected_stage}**"

        await interaction.response.send_message("✅ Advance started.", ephemeral=True)

        # Send the initial advance announcement with @everyone.
        # This is sent directly instead of through log_activity so the ping is guaranteed,
        # while last_reminder_day still prevents the immediate duplicate reminder ping.
        target_channel = get_output_channel(bot, interaction)

        if target_channel:
            embed = discord.Embed(
                title="🏈 Advance Timer Started",
                description=description,
                color=discord.Color.gold(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(
                text=f"Action by {interaction.user.display_name}"
            )

            await target_channel.send(
                content="@everyone",
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=True)
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
