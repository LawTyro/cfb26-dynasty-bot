import discord
from discord import app_commands

from backup_utils import create_database_backup
from utils import log_activity


def setup(tree, bot):
    backup_group = app_commands.Group(name="backup", description="Database backup commands")

    @backup_group.command(name="create", description="Create a manual database backup")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_create(interaction: discord.Interaction):
        try:
            backup_path = create_database_backup()

            await interaction.response.send_message(
                f"✅ Backup created:\n`{backup_path}`",
                ephemeral=True
            )
            await log_activity(
                bot,
                interaction,
                "💾 Backup Created",
                f"Database backup created at `{backup_path}`.",
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

    tree.add_command(backup_group)
