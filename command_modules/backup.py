import discord
from discord import app_commands

from backup_utils import create_database_backup


def setup(tree):
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

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Backup failed: `{e}`",
                ephemeral=True
            )

    tree.add_command(backup_group)
