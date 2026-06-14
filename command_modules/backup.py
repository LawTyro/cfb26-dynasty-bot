from datetime import datetime, timezone

import discord
from discord import app_commands

from backup_utils import (
    create_database_backup,
    list_database_backups,
    restore_database_backup,
    MAX_BACKUPS,
)
from utils import log_activity


async def backup_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    current = current.lower()
    choices = []

    for backup in list_database_backups():
        name = backup.name

        if current in name.lower():
            choices.append(app_commands.Choice(name=name, value=name))

        if len(choices) >= 25:
            break

    return choices


def setup(tree, bot):
    backup_group = app_commands.Group(name="backup", description="Database backup commands")

    @backup_group.command(name="create", description="Create a manual database backup")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_create(interaction: discord.Interaction):
        try:
            backup_path = create_database_backup()

            await interaction.response.send_message(
                f"✅ Backup created:\n`{backup_path}`\n\nKeeping the newest **{MAX_BACKUPS}** backups.",
                ephemeral=True
            )
            await log_activity(
                bot,
                interaction,
                "💾 Backup Created",
                f"Database backup created: `{backup_path.name}`.",
                discord.Color.green()
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Backup failed: `{e}`",
                ephemeral=True
            )
            await log_activity(
                bot,
                interaction,
                "❌ Backup Failed",
                f"Backup failed: `{e}`",
                discord.Color.red()
            )

    @backup_group.command(name="list", description="List available database backups")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_list(interaction: discord.Interaction):
        backups = list_database_backups()

        if not backups:
            return await interaction.response.send_message(
                "No backups found.",
                ephemeral=True
            )

        lines = []

        for index, backup in enumerate(backups, start=1):
            size_kb = backup.stat().st_size / 1024
            modified = datetime.fromtimestamp(backup.stat().st_mtime, timezone.utc)
            timestamp = discord.utils.format_dt(modified, style="f")
            lines.append(f"**{index}.** `{backup.name}` — {size_kb:.0f} KB — {timestamp}")

        embed = discord.Embed(
            title="📦 Available Backups",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Keeping newest {MAX_BACKUPS} backups")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @backup_group.command(name="restore", description="Restore the database from a backup")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.autocomplete(filename=backup_autocomplete)
    async def backup_restore(interaction: discord.Interaction, filename: str):
        try:
            restored_backup, pre_restore_backup = restore_database_backup(filename)

            await interaction.response.send_message(
                (
                    f"✅ Restored database from:\n`{restored_backup.name}`\n\n"
                    f"A pre-restore safety backup was created:\n`{pre_restore_backup.name}`\n\n"
                    "Restart the Railway service if anything looks stale."
                ),
                ephemeral=True
            )
            await log_activity(
                bot,
                interaction,
                "♻️ Backup Restored",
                f"Database restored from `{restored_backup.name}`.",
                discord.Color.gold()
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Restore failed: `{e}`",
                ephemeral=True
            )
            await log_activity(
                bot,
                interaction,
                "❌ Backup Restore Failed",
                f"Restore failed: `{e}`",
                discord.Color.red()
            )

    tree.add_command(backup_group)
