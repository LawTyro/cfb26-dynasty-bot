import discord
from discord import app_commands

import db
import embeds
from utils import log_activity


def setup(tree, bot):
    @tree.command(name="setchannel", description="Set bot announcement channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
        db.set_setting("channel_id", channel.id)

        await interaction.response.send_message(
            f"✅ Bot announcements will go to {channel.mention}.",
            ephemeral=True
        )
        await log_activity(
            bot,
            interaction,
            "📣 Bot Channel Set",
            f"Bot announcements and activity logs will go to {channel.mention}.",
            discord.Color.green()
        )

    @tree.command(name="status", description="Show dynasty status")
    async def status(interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=embeds.make_status_embed(interaction.guild)
        )

    @tree.command(name="help", description="Show commands")
    async def help_command(interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=embeds.make_help_embed(),
            ephemeral=True
        )
        await log_activity(
            bot,
            interaction,
            "❔ Help Viewed",
            f"{interaction.user.display_name} viewed the command help.",
            discord.Color.blue()
        )
