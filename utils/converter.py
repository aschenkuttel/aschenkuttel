from discord import app_commands
from .classes import _Keyword
import zoneinfo
import utils

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


class SummonerArg(app_commands.Transformer):
    __slots__ = ('key',)

    def __init__(self, shallow=False):
        self.shallow = shallow

    async def transform(self, interaction, value):
        if '#' not in value:
            raise utils.InvalidSummonerName(value)

        league = interaction.client.get_cog('League')

        if league is None:
            interaction.client.logger.error("league cog not loaded")
            raise utils.InvalidRiotResponse(999)

        name, tag = value.split('#')
        name, tag = name.strip(), tag.strip()

        if self.shallow:
            return await league.fetch_riot_acc_by_rid(name, tag)
        else:
            return await league.fetch_summoner_by_rid(name, tag)
