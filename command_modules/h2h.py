import discord
from discord import app_commands

import db
import embeds


def setup(tree):
    h2h_group = app_commands.Group(name="head2head", description="Head-to-head records")

    @h2h_group.command(name="add", description="Add a head-to-head result")
    @app_commands.checks.has_permissions(administrator=True)
    async def h2h_add(interaction: discord.Interaction, winner: discord.Member, loser: discord.Member):
        if winner.id == loser.id:
            return await interaction.response.send_message("Winner and loser cannot be the same.", ephemeral=True)

        if not db.is_player(winner.id) or not db.is_player(loser.id):
            return await interaction.response.send_message("Both users must be registered players.", ephemeral=True)

        db.add_h2h_game(winner.id, loser.id)

        embed = discord.Embed(
            title="🏈 Head-to-Head Result Added",
            description=f"**{winner.display_name}** defeated **{loser.display_name}**.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    @h2h_group.command(name="remove", description="Remove latest matching head-to-head result")
    @app_commands.checks.has_permissions(administrator=True)
    async def h2h_remove(interaction: discord.Interaction, winner: discord.Member, loser: discord.Member):
        removed = db.remove_latest_h2h_game(winner.id, loser.id)

        if not removed:
            return await interaction.response.send_message(
                f"No matching result found for {winner.display_name} over {loser.display_name}.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🧹 Head-to-Head Result Removed",
            description=f"Removed latest result: **{winner.display_name}** defeated **{loser.display_name}**.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

    @h2h_group.command(name="reset", description="Reset head-to-head records")
    @app_commands.checks.has_permissions(administrator=True)
    async def h2h_reset(
        interaction: discord.Interaction,
        player1: discord.Member = None,
        player2: discord.Member = None,
        all_players: bool = False
    ):
        if all_players:
            db.reset_h2h()

            embed = discord.Embed(
                title="🧹 Head-to-Head Records Reset",
                description="All head-to-head records have been deleted.",
                color=discord.Color.red()
            )

            return await interaction.response.send_message(embed=embed)

        if not player1 or not player2:
            return await interaction.response.send_message(
                "Provide both players or set all_players to True.",
                ephemeral=True
            )

        db.reset_h2h(player1.id, player2.id)

        embed = discord.Embed(
            title="🧹 Matchup Reset",
            description=f"Removed all games between **{player1.display_name}** and **{player2.display_name}**.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

    @h2h_group.command(name="view", description="View record between two players")
    async def h2h_view(interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
        if player1.id == player2.id:
            return await interaction.response.send_message("Choose two different players.", ephemeral=True)

        await interaction.response.send_message(
            embed=embeds.make_h2h_view_embed(player1, player2)
        )

    @h2h_group.command(name="player", description="View one player's head-to-head records")
    async def h2h_player(interaction: discord.Interaction, player: discord.Member = None):
        target = player or interaction.user

        await interaction.response.send_message(
            embed=embeds.make_h2h_player_embed(interaction.guild, target)
        )

    @h2h_group.command(name="standings", description="View overall head-to-head standings")
    async def h2h_standings(interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=embeds.make_h2h_standings_embed(interaction.guild)
        )

    tree.add_command(h2h_group)
