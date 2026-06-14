import discord
from discord import app_commands

import db


def setup(tree):
    player_group = app_commands.Group(name="player", description="Player management")

    @player_group.command(name="add", description="Add player")
    @app_commands.checks.has_permissions(administrator=True)
    async def player_add(interaction: discord.Interaction, member: discord.Member):
        if db.is_player(member.id):
            return await interaction.response.send_message("Already added.", ephemeral=True)

        db.add_player(member.id)
        await interaction.response.send_message(f"✅ Added {member.display_name}")

    @player_group.command(name="addall", description="Add all server members")
    @app_commands.checks.has_permissions(administrator=True)
    async def player_addall(interaction: discord.Interaction):
        added = 0
        skipped = 0

        for member in interaction.guild.members:
            if member.bot:
                skipped += 1
                continue

            if db.is_player(member.id):
                skipped += 1
                continue

            db.add_player(member.id)
            added += 1

        embed = discord.Embed(
            title="👥 Players Added",
            description=(
                f"✅ Added **{added}** player(s)\n"
                f"⏭️ Skipped **{skipped}** member(s)"
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    @player_group.command(name="remove", description="Remove player")
    @app_commands.checks.has_permissions(administrator=True)
    async def player_remove(interaction: discord.Interaction, member: discord.Member):
        if not db.is_player(member.id):
            return await interaction.response.send_message("Not found.", ephemeral=True)

        db.remove_player(member.id)
        await interaction.response.send_message(f"🛑 Removed {member.display_name}")

    @player_group.command(name="alias", description="Set a player's schedule/import alias")
    @app_commands.checks.has_permissions(administrator=True)
    async def player_alias(interaction: discord.Interaction, member: discord.Member, alias: str):
        if not db.is_player(member.id):
            return await interaction.response.send_message(
                "That user is not registered.",
                ephemeral=True
            )

        existing_user_id = db.get_user_id_by_alias(alias)

        if existing_user_id and existing_user_id != member.id:
            return await interaction.response.send_message(
                "That alias is already being used by another player.",
                ephemeral=True
            )

        db.set_player_alias(member.id, alias)
        await interaction.response.send_message(
            f"✅ Set alias for {member.display_name} to **{alias}**."
        )

    @player_group.command(name="clearalias", description="Clear a player's alias")
    @app_commands.checks.has_permissions(administrator=True)
    async def player_clearalias(interaction: discord.Interaction, member: discord.Member):
        if not db.is_player(member.id):
            return await interaction.response.send_message(
                "That user is not registered.",
                ephemeral=True
            )

        db.remove_player_alias(member.id)
        await interaction.response.send_message(
            f"🧹 Cleared alias for {member.display_name}."
        )

    @player_group.command(name="list", description="List players")
    async def player_list(interaction: discord.Interaction):
        ready_ids = set(db.get_ready_players())
        lines = []

        for uid in db.get_players():
            member = interaction.guild.get_member(uid)

            if not member:
                continue

            status = "✅" if uid in ready_ids else "❌"
            alias = db.get_player_alias(uid)

            if alias:
                lines.append(f"{status} {member.display_name} — alias: `{alias}`")
            else:
                lines.append(f"{status} {member.display_name}")

        embed = discord.Embed(
            title="👥 Dynasty Players",
            description="\n".join(lines) if lines else "No players.",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed)

    tree.add_command(player_group)
