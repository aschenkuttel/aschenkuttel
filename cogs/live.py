from discord.ext import commands, tasks
from bs4 import BeautifulSoup
import dateutil.parser
import discord
import asyncio
import json
import re


class LiveTicker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last = None
        self.url = "https://www.welt.de/vermischtes/live205334991/"
        # self.live_loop.start()

    @staticmethod
    def clean(raw_html):
        net = re.compile('<.*?>')
        subbed = re.sub(net, '', raw_html)
        result = re.sub(r'\n\s*\n', '\n', subbed)
        return " ".join(result.split())

    @tasks.loop(minutes=1)
    async def live_loop(self):
        try:
            cache = await self.bot.session.get(self.url)
            soup = BeautifulSoup(await cache.text(), 'html.parser')
            json_data = soup.find('script', {'data-qa': "StructuredData"})

            if json_data is None:
                return

            archive = json.loads(json_data.text)
            last_post = archive['liveBlogUpdate'][0]
        except Exception as error:
            print(error)
            return

        date = dateutil.parser.parse(last_post['datePublished'])
        if self.last == date.timestamp():
            return
        else:
            self.last = date.timestamp()

        desc = self.clean(last_post['articleBody'])

        if not desc:
            self.last = None
            return

        if len(desc) > 2040:
            return

        title, url = last_post['headline'], last_post['url']
        embed = discord.Embed(title=title, description=desc, url=url)
        embed.timestamp = date

        for guild in self.bot.guilds:
            channel_id = self.bot.config.get_item(guild.id, 'liveticker')
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                print("FORBIDDEN :(")
                pass

    @live_loop.before_loop
    async def before_live(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)


def setup(bot):
    bot.add_cog(LiveTicker(bot))
