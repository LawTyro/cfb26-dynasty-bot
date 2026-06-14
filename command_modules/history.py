import discord
from discord import app_commands

import db


def setup(tree):
    history_group = app_commands.Group(name="history", description="Team history commands")

    @history_group.command(name="view", description="View team history")
    async def history_view(interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        teams = db.get_history(target.id)

        embed = discord.Embed(
            title=f"🏈 {target.display_name}'s Team History",
            color=discord.Color.blue()
        )

        embed.description = (
            "\n".join(f"- {team}" for team in teams)
            if teams
            else "No team history yet."
        )

        await interaction.response.send_message(embed=embed)

    @history_group.command(name="all", description="Show all histories")
    async def history_all(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏈 Team Histories",
            color=discord.Color.blue()
        )

        added = 0

        for uid in db.get_players():
            member = interaction.guild.get_member(uid)

            if not member:
                continue

            teams = db.get_history(uid)

            embed.add_field(
                name=member.display_name,
                value="\n".join(f"- {team}" for team in teams) if teams else "No team history",
                inline=False
            )

            added += 1

            if added >= 25:
                break

        if added == 0:
            embed.description = "No players found."

        await interaction.response.send_message(embed=embed)

    @history_group.command(name="add", description="Add team history")
    @app_commands.checks.has_permissions(administrator=True)
    async def history_add(interaction: discord.Interaction, member: discord.Member, team: str):
        if not db.is_player(member.id):
            return await interaction.response.send_message("That player is not registered.", ephemeral=True)

        added = db.add_history(member.id, team)

        if not added:
            return await interaction.response.send_message(
                f"**{team}** already exists in {member.display_name}'s history.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"🏈 Added **{team}** to {member.display_name}'s history."
        )

    @history_group.command(name="remove", description="Remove team history")
    @app_commands.checks.has_permissions(administrator=True)
    async def history_remove(interaction: discord.Interaction, member: discord.Member, team: str):
        removed = db.remove_history(member.id, team)

        if not removed:
            return await interaction.response.send_message(f"**{team}** not found.", ephemeral=True)

        await interaction.response.send_message(
            f"🧹 Removed **{removed}** from {member.display_name}'s history."
        )

    @history_group.command(name="reset", description="Reset history")
    @app_commands.checks.has_permissions(administrator=True)
    async def history_reset(
        interaction: discord.Interaction,
        member: discord.Member = None,
        all_players: bool = False
    ):
        if all_players:
            db.reset_history()
            return await interaction.response.send_message("🧹 Reset history for all players.")

        target = member or interaction.user
        db.reset_history(target.id)
        await interaction.response.send_message(f"🧹 Reset history for {target.display_name}.")

    tree.add_command(history_group)
