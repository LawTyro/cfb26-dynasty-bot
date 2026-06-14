import discord

import db


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


def get_output_channel(bot, interaction=None):
    channel_id = db.get_setting("channel_id", "")

    if channel_id:
        channel = bot.get_channel(int(channel_id))

        if channel:
            return channel

    if interaction:
        return interaction.channel

    return None


def format_schedule_opponent(opponent):
    display = str(opponent).strip()

    if display.lower().startswith("at "):
        return "@ " + display[3:].strip()

    return display


def format_current_schedule_line(name, opponent, is_user_game):
    display = format_schedule_opponent(opponent)

    if display.startswith("@ "):
        line = f"🏈 {name} - {display}"
    else:
        line = f"🏈 {name} - vs {display}"

    if is_user_game:
        line += " *"

    return line


async def maybe_send_everyone_ready(bot, interaction):
    if not db.get_setting("advance_end", ""):
        return

    if not everyone_ready():
        return

    if db.get_bool_setting("all_ready_sent"):
        return

    db.set_bool_setting("all_ready_sent", True)

    channel = get_output_channel(bot, interaction)

    if channel:
        commissioner_role = discord.utils.get(channel.guild.roles, name="Commissioner")
        commissioner_ping = commissioner_role.mention if commissioner_role else "@Commissioner"

        embed = discord.Embed(
            title="🏈 Everyone Is Ready!",
            description="Commissioners can advance the league.",
            color=discord.Color.green(),
        )

        await channel.send(
            commissioner_ping,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )


async def log_activity(bot, interaction, title, description=None, color=None, mention=None, allowed_mentions=None):
    channel = get_output_channel(bot, interaction)

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description or discord.Embed.Empty,
        color=color or discord.Color.blue(),
    )

    if interaction and interaction.user:
        embed.set_footer(text=f"Action by {interaction.user.display_name}")

    await channel.send(
        content=mention,
        embed=embed,
        allowed_mentions=allowed_mentions
    )
