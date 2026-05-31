import os
import math
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from discord import app_commands

import db
import embeds

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

ADVANCE_STAGES = [
    "Preseason",
    "Week 0",
    "Week 1",
    "Week 2",
    "Week 3",
    "Week 4",
    "Week 5",
    "Week 6",
    "Week 7",
    "Week 8",
    "Week 9",
    "Week 10",
    "Week 11",
    "Week 12",
    "Week 13",
    "Week 14",
    "Week 15",
    "Conference Championship",
    "Bowl Week 1",
    "Bowl Week 2",
    "Bowl Week 3",
    "Bowl Week 4"
    "Offseason Portal Week 1",
    "Offseason Portal Week 2",
    "Offseason Portal Week 3",
    "Offseason Portal Week 4",
    "National Signing Day",
    "Training Results",
    "Encourage Transfers",
]


def everyone_ready():
    players = db.get_players()

    if not players:
        return False

    ready_players = set(db.get_ready_players())

    return all(player in ready_players for player in players)


def get_unready_mentions():
    ready_players = set(db.get_ready_players())

    return [
        f"<@{uid}>"
        for uid in db.get_players()
        if uid not in ready_players
    ]


async def reminder_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            remaining = embeds.get_remaining()

            if remaining:
                seconds = remaining.total_seconds()

                if seconds <= 0:
                    channel_id = db.get_setting("channel_id", "")
                    channel = bot.get_channel(int(channel_id)) if channel_id else None

                    if channel:
                        embed = discord.Embed(
                            title="🚨 Dynasty Is Advancing Now!",
                            description="The advance timer has expired.",
                            color=discord.Color.red(),
                            timestamp=datetime.now(timezone.utc)
                        )

                        await channel.send(
                            "@everyone",
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(everyone=True)
                        )

                    db.set_setting("advance_end", "")
                    db.clear_ready()
                    db.set_bool_setting("all_ready_sent", False)

                else:
                    days_left = math.ceil(seconds / 86400)
                    last_reminder_day = db.get_setting("last_reminder_day", "")

                    if str(days_left) != str(last_reminder_day):
                        db.set_setting("last_reminder_day", days_left)

                        channel_id = db.get_setting("channel_id", "")
                        channel = bot.get_channel(int(channel_id)) if channel_id else None

                        if channel:
                            unready = get_unready_mentions()

                            embed = discord.Embed(
                                title="🏈 Advance Reminder",
                                description=f"**{days_left} day(s) until advance**",
                                color=discord.Color.gold(),
                                timestamp=datetime.now(timezone.utc)
                            )

                            if unready:
                                embed.add_field(
                                    name="❌ Still Waiting On",
                                    value="\n".join(unready),
                                    inline=False
                                )

                                await channel.send(
                                    " ".join(unready),
                                    embed=embed,
                                    allowed_mentions=discord.AllowedMentions(users=True)
                                )
                            else:
                                embed.add_field(
                                    name="✅ Everyone Is Ready",
                                    value="No one is left to ready up.",
                                    inline=False
                                )

                                await channel.send(embed=embed)

        except Exception as e:
            print("Reminder error:", e)

        await asyncio.sleep(60)


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


@player_group.command(name="list", description="List players")
async def player_list(interaction: discord.Interaction):
    ready_ids = set(db.get_ready_players())
    lines = []

    for uid in db.get_players():
        member = interaction.guild.get_member(uid)

        if not member:
            continue

        status = "✅" if uid in ready_ids else "❌"
        lines.append(f"{status} {member.display_name}")

    embed = discord.Embed(
        title="👥 Dynasty Players",
        description="\n".join(lines) if lines else "No players.",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed)


tree.add_command(player_group)


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


@tree.command(name="advance", description="Start/reset advance timer")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.choices(stage=[
    app_commands.Choice(name=stage, value=stage)
    for stage in ADVANCE_STAGES
])
async def advance(
    interaction: discord.Interaction,
    stage: app_commands.Choice[str] = None
):
    days = int(db.get_setting("advance_days", "4"))
    new_end = datetime.now(timezone.utc) + timedelta(days=days)
    selected_stage = stage.value if stage else ""

    db.set_setting("advance_end", new_end.isoformat())
    db.set_setting("channel_id", interaction.channel.id)
    db.set_setting("last_reminder_day", "")
    db.set_bool_setting("all_ready_sent", False)
    db.set_setting("advance_stage", selected_stage)
    db.clear_ready()

    description = f"Advance is in **{days} day(s)**."

    if selected_stage:
        description += f"\nAdvanced to: **{selected_stage}**"

    embed = discord.Embed(
        title="🏈 Advance Timer Started",
        description=description,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    await interaction.response.send_message(
        "@everyone",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(everyone=True)
    )


@tree.command(name="cancel", description="Cancel advance")
@app_commands.checks.has_permissions(administrator=True)
async def cancel(interaction: discord.Interaction):
    db.set_setting("advance_end", "")
    db.clear_ready()
    db.set_bool_setting("all_ready_sent", False)

    embed = discord.Embed(
        title="🛑 Advance Cancelled",
        description="The current advance timer has been cancelled.",
        color=discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)


@tree.command(name="extend", description="Extend timer")
@app_commands.checks.has_permissions(administrator=True)
async def extend(interaction: discord.Interaction, days: int):
    remaining = embeds.get_remaining()

    if not remaining:
        return await interaction.response.send_message("No active advance.", ephemeral=True)

    new_end = datetime.now(timezone.utc) + remaining + timedelta(days=days)

    db.set_setting("advance_end", new_end.isoformat())
    db.set_setting("last_reminder_day", "")

    embed = discord.Embed(
        title="⏳ Advance Timer Extended",
        description=f"Extended by **{days} day(s)**.",
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)


@tree.command(name="setdays", description="Set default advance days")
@app_commands.checks.has_permissions(administrator=True)
async def setdays(interaction: discord.Interaction, days: int):
    if days <= 0:
        return await interaction.response.send_message("Days must be greater than 0.", ephemeral=True)

    db.set_setting("advance_days", days)

    embed = discord.Embed(
        title="✅ Default Advance Length Updated",
        description=f"Default advance length set to **{days} day(s)**.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed)


@tree.command(name="ready", description="Mark ready")
async def ready(interaction: discord.Interaction):
    uid = interaction.user.id

    if not db.is_player(uid):
        return await interaction.response.send_message("Not registered.", ephemeral=True)

    if uid in db.get_ready_players():
        return await interaction.response.send_message("Already ready.", ephemeral=True)

    db.mark_ready(uid)

    await interaction.response.send_message("✅ Ready!")

    if db.get_setting("advance_end", "") and everyone_ready() and not db.get_bool_setting("all_ready_sent"):
        db.set_bool_setting("all_ready_sent", True)

        channel_id = db.get_setting("channel_id", "")
        channel = bot.get_channel(int(channel_id)) if channel_id else None

        if channel:
            commissioner_role = discord.utils.get(channel.guild.roles, name="Commissioners")
            commissioner_ping = commissioner_role.mention if commissioner_role else "@Commissioners"

            embed = discord.Embed(
                title="🏈 Everyone Is Ready!",
                description="Commissioners can advance the league.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )

            await channel.send(
                commissioner_ping,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True)
            )


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

    embed = discord.Embed(
        title="🧹 Ready Status Cleared",
        description="All players have been marked not ready.",
        color=discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)


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


@bot.event
async def on_ready():
    db.init_db()
    db.migrate_json_if_needed()

    await tree.sync()

    print(f"Logged in as {bot.user}")

    if not hasattr(bot, "reminder_task"):
        bot.reminder_task = asyncio.create_task(reminder_loop())


bot.run(TOKEN)
