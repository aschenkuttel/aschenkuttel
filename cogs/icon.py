from data.credentials import UNSPLASH_KEY
from utils import get_seconds_till
from discord.ext import commands
import asyncio
import discord


class Icon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = "https://api.unsplash.com/photos/random"
        self.bot.loop.create_task(self.guild_icon_loop())

    async def guild_icon_loop(self):
        while not self.bot.is_closed():
            sec = get_seconds_till(days=1)
            await asyncio.sleep(sec)

            for guild in self.bot.guilds:
                key = self.bot.config.get('query', guild.id)
                enabled = self.bot.config.get('icon', guild.id)

                if key is None or not enabled:
                    continue

                payload = {'query': key}
                auth = {'Authorization': UNSPLASH_KEY}
                async with self.bot.session.get(self.url, params=payload, headers=auth) as r:
                    data = await r.json()

                    try:
                        small_url = data['urls']['small']
                        async with self.bot.session.get(small_url) as resp:
                            cache = await resp.read()

                    except KeyError:
                        continue

                try:
                    await guild.edit(icon=cache)

                except discord.Forbidden:
                    continue

            await asyncio.sleep(1)


def setup(bot):
    bot.add_cog(Icon(bot))
