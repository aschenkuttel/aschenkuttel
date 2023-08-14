from discord import app_commands
from .classes import _Keyword
import zoneinfo

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


class Keyword(app_commands.Transformer):
    __slots__ = ('sign', 'value', 'compare')

    async def transform(self, interaction, value):
        return _Keyword(value)


class TimeZone(app_commands.Transformer):
    __slots__ = ('key',)

    async def autocomplete(self, interaction, value):
        return [app_commands.Choice(name=str(tz), value=str(tz)) for tz in zoneinfo.available_timezones()
                if value.lower() in str(tz).lower()][:25]

    async def transform(self, interaction, value):
        return zoneinfo.ZoneInfo(value)