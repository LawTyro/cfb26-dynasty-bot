from datetime import datetime, timezone

import discord
from discord import app_commands

import db
from utils import get_output_channel, maybe_send_everyone_ready


def setup(tree, bot):
    @tree.command(name="ready", description="Mark ready")
    async def ready(interaction: discord.Interaction):
        uid = interaction.user.id

        if not db.is_player(uid):
            return await interaction.response.send_message("Not registered.", ephemeral=True)

        if uid in db.get_ready_players():
            return await interaction.response.send_message("Already ready.", ephemeral=True)

        db.mark_ready(uid)
        await interaction.response.send_message("✅ Ready!")
        await maybe_send_everyone_ready(bot, interaction)

    @tree.command(name="setready", description="Mark another player as ready")
    @app_commands.checks.has_permissions(administrator=True)
    async def setready(interaction: discord.Interaction, member: discord.Member):
        if not db.is_player(member.id):
            return await interaction.response.send_message(
                "That user is not registered.",
                ephemeral=True
            )

        if member.id in db.get_ready_players():
            return await interaction.response.send_message(
                f"{member.display_name} is already ready.",
                ephemeral=True
            )

        db.mark_ready(member.id)

        await interaction.response.send_message(
            f"✅ Marked {member.display_name} as ready.",
            ephemeral=True
        )

        await maybe_send_everyone_ready(bot, interaction)

    @tree.command(name="unready", description="Mark unready")
    async def unready(interaction: discord.Interaction):
        db.mark_unready(interaction.user.id)
        db.set_bool_setting("all_ready_sent", False)

        await interaction.response.send_message("↩️ Unready")

    @tree.command(name="clearready", description="Clear all ready statuses")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearready(interaction: discord.Interaction):
        db.clear_ready()
        db.set_bool_setting("all_ready_sent", False)

        target_channel = get_output_channel(bot, interaction)

        embed = discord.Embed(
            title="🧹 Ready Status Cleared",
            description="All players have been marked not ready.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        await target_channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Ready statuses cleared and posted in {target_channel.mention}.",
            ephemeral=True
        )
