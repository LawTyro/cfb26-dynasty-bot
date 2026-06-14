from discord import app_commands

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
    "Bowl Week 4",
    "Offseason Portal Week 1",
    "Offseason Portal Week 2",
    "Offseason Portal Week 3",
    "Offseason Portal Week 4",
]


async def stage_autocomplete(interaction, current: str):
    current = current.lower()

    return [
        app_commands.Choice(name=stage, value=stage)
        for stage in ADVANCE_STAGES
        if current in stage.lower()
    ][:25]
