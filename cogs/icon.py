from utils import get_seconds, IconHandler
from discord.ext import commands
from data.secret import API_KEY
import asyncio
import discord


class Icon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = "https://api.unsplash.com/photos/random"
        self.bot.loop.create_task(self.guild_icon_loop())
        self.archive = IconHandler()

    async def guild_icon_loop(self):
        while not self.bot.is_closed():
            sec = get_seconds()
            await asyncio.sleep(sec)
            for guild in self.bot.guilds:
                key = self.bot.config.get_item(guild.id, 'query')
                if not key:
                    continue
                payload = {'query': key}
                auth = {'Authorization': API_KEY}
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

    @commands.command(name="query")
    async def query_(self, ctx, query):
        self.bot.config.save_item(ctx.guild.id, 'query', query)
        msg = f"Das neue Schlagwort wurde registriert"
        await ctx.send(msg)


def setup(bot):
    bot.add_cog(Icon(bot))
