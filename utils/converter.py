from discord import app_commands

config_options = [
    app_commands.Choice(name="lobby", value="lobby"),
    app_commands.Choice(name="bdayboard", value="bdayboard"),
    app_commands.Choice(name="starboard", value="starboard"),
    app_commands.Choice(name="starcount", value="starcount"),
    app_commands.Choice(name="leagueboard", value="league")
]

config_features = [
    app_commands.Choice(name="Join/Leave Sound", value="sound"),
]
